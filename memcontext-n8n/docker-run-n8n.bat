@echo off
chcp 65001 >nul
REM Docker 运行 n8n，挂载本地 n8ndemo 目录
REM 这样 Docker 中的 n8n 可以访问本地的 n8ndemo 文件夹

echo 正在检查 Docker 状态...
docker ps >nul 2>&1
if errorlevel 1 (
    echo.
    echo [错误] Docker Desktop 未运行！
    echo.
    echo 请先启动 Docker Desktop：
    echo 1. 按 Win 键，搜索 "Docker Desktop" 并启动
    echo 2. 或运行: start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo 3. 等待 Docker Desktop 完全启动后，再运行此脚本
    echo.
    pause
    exit /b 1
)

echo Docker 运行正常！
echo.

REM 检查端口 5678 是否被占用
netstat -ano | findstr :5678 >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口 5678 已被占用！
    echo.
    echo 正在检查是否有 n8n 容器在运行...
    docker ps -a --filter "name=n8n" --format "{{.Names}}" | findstr n8n >nul 2>&1
    if not errorlevel 1 (
        echo 发现 n8n 容器，正在停止并删除...
        docker stop n8n >nul 2>&1
        docker rm n8n >nul 2>&1
        echo 已清理旧容器，等待 2 秒...
        timeout /t 2 /nobreak >nul
    ) else (
        echo 未找到 n8n 容器，可能是其他程序占用了端口 5678
        echo 请手动停止占用端口的程序，或修改脚本使用其他端口
        echo.
        pause
        exit /b 1
    )
)

echo 正在启动 n8n Docker 容器...
echo.
echo ========================================
echo 挂载配置：
echo ========================================
echo 本地路径: %CD%\n8ndemo
echo 容器路径: /home/node/n8ndemo
echo.
echo 说明：
echo - 容器端口: 5678 (n8n Web UI)
echo - 本地 n8ndemo 目录已挂载到容器的 /home/node/n8ndemo
echo - 容器可以通过 host.docker.internal:5019 访问本地 n8ndemo 服务
echo ========================================
echo.

docker run -it --rm ^
  --name n8n ^
  -p 5678:5678 ^
  -v "%CD%\n8ndemo":/home/node/n8ndemo ^
  -e N8N_BASIC_AUTH_ACTIVE=true ^
  -e N8N_BASIC_AUTH_USER=admin ^
  -e N8N_BASIC_AUTH_PASSWORD=admin ^
  -e NODE_ENV=production ^
  n8nio/n8n

pause

