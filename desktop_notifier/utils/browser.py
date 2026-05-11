"""浏览器工具模块 — 用于在默认浏览器中打开前端页面"""
import webbrowser


def open_frontend(server_base_url: str, path: str = "/"):
    """
    在默认浏览器中打开前端页面。

    :param server_base_url: 后端地址（如 http://127.0.0.1:8000）
    :param path: 前端页面路径（如 /control-panel/system-update）
    """
    if ":8000" in server_base_url:
        frontend_url = server_base_url.replace(":8000", ":3000") + path
    else:
        frontend_url = server_base_url + path
    webbrowser.open(frontend_url)
