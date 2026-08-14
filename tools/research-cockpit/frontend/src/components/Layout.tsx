import { BookOpen, Bot, Command, Gauge, Menu, ShieldCheck, Target, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";

const items = [
  { to: "/", label: "今日驾驶舱", icon: Gauge },
  { to: "/ask", label: "只读智能体", icon: Bot },
  { to: "/library", label: "资料检索", icon: BookOpen },
  { to: "/predictions", label: "预测追踪", icon: Target },
];

export default function Layout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="app-shell">
      <button className="mobile-menu" onClick={() => setOpen(true)} aria-label="打开导航">
        <Menu size={20} />
      </button>
      {open && <button className="scrim" onClick={() => setOpen(false)} aria-label="关闭导航" />}
      <aside className={`sidebar ${open ? "is-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Command size={20} /></div>
          <div>
            <strong>INFINITY</strong>
            <span>RESEARCH COCKPIT</span>
          </div>
          <button className="sidebar-close" onClick={() => setOpen(false)} aria-label="关闭导航"><X /></button>
        </div>
        <nav>
          <span className="nav-label">工作台</span>
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} onClick={() => setOpen(false)} className={({ isActive }) => isActive ? "active" : ""}>
              <Icon size={18} strokeWidth={1.8} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <ShieldCheck size={17} />
          <div><strong>Local · Read only</strong><span>Vault 永远是事实源</span></div>
        </div>
      </aside>
      <main className="main-stage">{children}</main>
    </div>
  );
}
