# -*- coding: utf-8 -*-
"""黄哥宏观指标看板 · 数据抓取与页面生成
用法: python generate.py  → 输出 dashboard.html（同目录）
数据源: FRED 公开 CSV (fredgraph.csv, 无需 API key)
阈值出处: 黄哥 260511 终端现金流监测器 / 260518 危机同构 / 260618 沃什 / 260611 黄金
"""
import json
import os
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={}"
UA = {"User-Agent": "Mozilla/5.0 (dashboard-generator)"}


def fetch(series_id, retries=3):
    """返回 [(date_str, float), ...]，跳过缺失值；失败重试"""
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(FRED.format(series_id), headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                text = r.read().decode("utf-8")
            break
        except Exception as e:
            last_err = e
            time.sleep(2 * (i + 1))
    else:
        raise last_err
    out = []
    for line in text.strip().splitlines()[1:]:
        d, _, v = line.partition(",")
        v = v.strip()
        if v and v != ".":
            try:
                out.append((d, float(v)))
            except ValueError:
                pass
    return out


def yoy(rows):
    """月度序列 → 同比% 序列（保留日期）"""
    idx = {d[:7]: v for d, v in rows}
    out = []
    for d, v in rows:
        y, m = int(d[:4]) - 1, d[5:7]
        prev = idx.get(f"{y}-{m}")
        if prev:
            out.append((d, (v / prev - 1) * 100))
    return out


def spark(rows, n=40):
    vals = [v for _, v in rows[-n:]]
    return [round(v, 2) for v in vals]


def pct(a, b):
    return (a / b - 1) * 100 if b else 0


def make(rows, unit="", digits=2, status=None, reason="", spark_rows=None, extra=""):
    """组装单个指标的数据对象"""
    d, v = rows[-1]
    pv = rows[-2][1] if len(rows) > 1 else v
    return {
        "value": round(v, digits),
        "prev": round(pv, digits),
        "unit": unit,
        "date": d,
        "status": status or "neutral",
        "reason": reason,
        "extra": extra,
        "spark": spark(spark_rows if spark_rows is not None else rows),
    }


def publish_page(payload):
    """只在完整页面就绪后替换旧版；临时文件与目标位于同一文件系统。"""
    temporary = None
    try:
        template = (HERE / "template.html").read_text(encoding="utf-8")
        marker = "/*__DATA__*/null"
        if template.count(marker) != 1:
            raise ValueError("模板必须包含且只包含一个数据占位符")
        html = template.replace(marker, json.dumps(payload, ensure_ascii=False, allow_nan=False))
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=HERE,
            prefix=".dashboard-", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(html)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(HERE / "dashboard.html")
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main():
    try:
        return generate()
    except Exception as exc:
        print(f"FAIL 刷新失败，未发布新页面：{type(exc).__name__}: {exc}")
        return 1


def generate():
    data, errors = {}, []

    def safe(key, fn):
        try:
            data[key] = fn()
        except Exception as e:  # 收集失败原因，任何失败都会阻止发布
            errors.append(f"{key}: {e}")

    # ── 支付端 ──
    def _rsafs():
        rows = fetch("RSAFS")
        mom = pct(rows[-1][1], rows[-2][1])
        yy = yoy(rows)
        obj = make(rows, "$M", 0, extra=f"环比 {mom:+.2f}% ｜ 同比 {yy[-1][1]:+.2f}%")
        obj["yoy"] = round(yy[-1][1], 2)
        return obj
    safe("rsafs", _rsafs)

    def _umcsent():
        rows = fetch("UMCSENT")
        chg = rows[-1][1] - rows[-2][1]
        return make(rows, "", 1, extra=f"较上月 {chg:+.1f}")
    safe("umcsent", _umcsent)

    # ── 价格压力: CPI 同比 ──
    def _cpi():
        rows = yoy(fetch("CPIAUCSL"))
        v = rows[-1][1]
        s = "good" if v <= 2.4 else ("warn" if v <= 3.2 else "alert")
        return make(rows, "%", 2, s, "2%轨道内" if s == "good" else "偏离2%轨道")
    safe("cpi_yoy", _cpi)

    # ── 物流库存 ──
    def _irsa():
        rows = fetch("RETAILIRSA")
        v = rows[-1][1]
        s = "good" if v <= 1.25 else ("warn" if v <= 1.35 else "alert")
        return make(rows, "", 2, s, "<1.25 健康" if s == "good" else (">1.35 积压预警" if s == "alert" else "1.25-1.35 观察带"))
    safe("retailirsa", _irsa)

    def _orders():
        rows = fetch("AMTMNO")
        m1 = pct(rows[-1][1], rows[-2][1])
        m2 = pct(rows[-2][1], rows[-3][1])
        if m1 > 0 and m2 > 0:
            s, r = "good", "连续2月上行=扩张意愿"
        elif m1 < 0 and m2 < 0:
            s, r = "warn", "连续2月下行=收缩"
        else:
            s, r = "neutral", "方向未定"
        return make(rows, "$M", 0, s, r, extra=f"近两月环比 {m2:+.1f}% → {m1:+.1f}%")
    safe("amtmno", _orders)

    # ── 宏观辅助 ──
    safe("wti", lambda: make(fetch("DCOILWTICO"), "$", 2))
    safe("dollar", lambda: make(fetch("DTWEXBGS"), "", 2))

    def _dgs10():
        rows = fetch("DGS10")
        v = rows[-1][1]
        s = "alert" if v >= 5 else ("warn" if v >= 4.5 else "good")
        return make(rows, "%", 2, s, "突破5%死亡线" if s == "alert" else ("逼近5%死亡线" if s == "warn" else "距5%死亡线尚有空间"))
    safe("dgs10", _dgs10)

    # ── 危机预警层 ──
    def _hy():
        rows = fetch("BAMLH0A0HYM2")
        v = rows[-1][1]
        s = "alert" if v >= 5 else ("warn" if v >= 4 else "good")
        return make(rows, "%", 2, s, ">5% 风险偏好收缩" if s == "alert" else ("接近5%阈值" if s == "warn" else "风险偏好正常"))
    safe("hy_spread", _hy)

    def _ccc():
        rows = fetch("BAMLH0A3HYC")
        v = rows[-1][1]
        base = [x for d, x in rows[-22:]]  # 约一个月交易日
        chg30 = v - base[0]
        s = "alert" if chg30 >= 1.0 else ("warn" if chg30 >= 0.5 else "good")
        return make(rows, "%", 2, s,
                    "30日快速上升=最弱环节承压" if s != "good" else "未见拐点式上升",
                    extra=f"30日变化 {chg30:+.2f}pp")
    safe("ccc_spread", _ccc)

    def _bizdef():
        rows = fetch("DRBLACBS")
        v = rows[-1][1]
        s = "alert" if v >= 8 else ("warn" if v >= 3 else "good")
        return make(rows, "%", 2, s, "接近历史峰值" if s == "alert" else ("趋势性抬升" if s == "warn" else "违约率低位"))
    safe("biz_default", _bizdef)

    def _ccdef():
        rows = fetch("DRCCLACBS")
        v = rows[-1][1]
        s = "alert" if v >= 5 else ("warn" if v >= 3.5 else "good")
        return make(rows, "%", 2, s, "总体口径；18-29岁分层需查纽联储季报")
    safe("cc_default", _ccdef)

    # ── 沃什三指标 ──
    def _payems():
        rows = fetch("PAYEMS")
        diff = [(rows[i][0], rows[i][1] - rows[i - 1][1]) for i in range(1, len(rows))]
        v = diff[-1][1]
        s = "alert" if v < 0 else ("warn" if v < 100 else "good")
        return make(diff, "千人", 0, s, "就业收缩" if s == "alert" else ("明显降温" if s == "warn" else "就业稳健"))
    safe("payems", _payems)

    def _unrate():
        rows = fetch("UNRATE")
        v = rows[-1][1]
        low12 = min(x for _, x in rows[-12:])
        gap = v - low12
        s = "alert" if gap >= 0.5 else ("warn" if gap >= 0.3 else "good")
        return make(rows, "%", 1, s, f"较12月低点 +{gap:.1f}pp" + ("（类Sahm预警）" if s == "alert" else ""))
    safe("unrate", _unrate)

    def _pce():
        rows = yoy(fetch("PCEPILFE"))
        v = rows[-1][1]
        s = "good" if v <= 2.2 else ("warn" if v <= 3 else "alert")
        return make(rows, "%", 2, s, "回到2%轨道" if s == "good" else "未回2%承诺轨道")
    safe("core_pce", _pce)

    # ── 黄金四对手盘 ──
    safe("real_yield", lambda: make(fetch("DFII10"), "%", 2, extra="上行=黄金机会成本↑"))
    safe("breakeven", lambda: make(fetch("T10YIE"), "%", 2, extra="回落过快=通缩风险"))
    safe("sp500", lambda: make(fetch("SP500"), "", 0, extra="股市强=资金弃金投股"))

    # 后处理: 实际零售增速 = 名义零售同比 − CPI同比（黄哥价格压力模块的"通胀调整逻辑"）
    if "rsafs" in data and "cpi_yoy" in data:
        real = data["rsafs"]["yoy"] - data["cpi_yoy"]["value"]
        s = "good" if real > 0.5 else ("warn" if real >= -0.5 else "alert")
        data["rsafs"]["status"] = s
        data["rsafs"]["reason"] = {"good": "实际零售正增长", "warn": "实际零售停滞（±0.5%内）", "alert": "实际零售负增长"}[s]
        data["rsafs"]["extra"] += f" ｜ 实际同比 {real:+.2f}%"

    payload = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "errors": errors,
        "series": data,
    }

    print(f"   序列 {len(data)} 个成功, {len(errors)} 个失败")
    for e in errors:
        print("   FAIL", e)
    if errors or not data:
        print("FAIL 指标未全部成功，保留原有页面及生成时间。")
        return 1
    publish_page(payload)
    print(f"OK 生成 {HERE / 'dashboard.html'}")
    # 汇总预警供日报引用
    lights = {k: v["status"] for k, v in data.items() if v["status"] in ("alert", "warn")}
    print("   预警/关注:", json.dumps(lights, ensure_ascii=False) if lights else "无")
    return 0


if __name__ == "__main__":
    sys.exit(main())
