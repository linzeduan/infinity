@echo off
chcp 65001 >nul
title Infinity Research Cockpit
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\research-cockpit\launch.ps1"
