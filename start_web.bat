@echo off
title SmartCrawler Studio - Local Web Engine
echo ============================================================
echo  Menjalankan SmartCrawler Studio (Local-First Web Crawler)
echo  Buka Browser di: http://localhost:8000
echo ============================================================
start http://localhost:8000
.\venv\Scripts\python app.py
pause
