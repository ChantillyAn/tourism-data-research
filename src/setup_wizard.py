"""引导式配置 — LLM + 搜索引擎"""

from __future__ import annotations

from pathlib import Path

from src.config import LLM_API_KEY, LLM_PROVIDERS, ROOT_DIR, SEARCH_PROVIDERS

_ENV_PATH = ROOT_DIR / ".env"


def run_setup() -> None:
    """交互式配置"""
    print("\n=== 文旅数据研究工具 — 初始配置 ===\n")

    env_vars: dict[str, str] = {}

    # ── 第一步：LLM ──
    print("【第一步】配置 LLM（大语言模型）\n")

    providers = list(LLM_PROVIDERS.items())
    print("选择 LLM 提供商：")
    for i, (key, info) in enumerate(providers, 1):
        print(f"  {i}. {info['name']} ({key})")
    print(f"  {len(providers) + 1}. 自定义（兼容 OpenAI 格式的任意服务）")

    while True:
        choice = input(f"\n请输入编号 [1-{len(providers) + 1}]（默认 1）：").strip()
        if not choice:
            choice = "1"
        try:
            idx = int(choice)
            if 1 <= idx <= len(providers) + 1:
                break
        except ValueError:
            pass
        print("无效输入，请重试")

    if idx <= len(providers):
        provider_key, provider_info = providers[idx - 1]
        base_url = provider_info["base_url"]
        default_model = provider_info["default_model"]
        print(f"\n已选择: {provider_info['name']}")
    else:
        provider_key = "custom"
        base_url = input("请输入 API Base URL：").strip()
        default_model = input("请输入模型名称：").strip()

    api_key = input("\n请输入 LLM API Key：").strip()
    if not api_key:
        print("未输入 API Key，配置取消")
        return

    model = input(f"模型名称（默认 {default_model}）：").strip() or default_model

    env_vars.update({
        "LLM_PROVIDER": provider_key,
        "LLM_API_KEY": api_key,
        "LLM_BASE_URL": base_url,
        "LLM_MODEL": model,
    })

    # ── 第二步：搜索引擎 ──
    print("\n【第二步】配置搜索引擎\n")

    search_providers = list(SEARCH_PROVIDERS.items())
    print("选择搜索引擎：")
    for i, (key, info) in enumerate(search_providers, 1):
        print(f"  {i}. {info['name']} — {info['description']}")

    while True:
        choice = input(f"\n请输入编号 [1-{len(search_providers)}]（默认 3，免费）：").strip()
        if not choice:
            choice = str(len(search_providers))  # 默认选最后一个（ddgs）
        try:
            idx = int(choice)
            if 1 <= idx <= len(search_providers):
                break
        except ValueError:
            pass
        print("无效输入，请重试")

    search_key, search_info = search_providers[idx - 1]
    print(f"\n已选择: {search_info['name']}")

    env_vars["SEARCH_PROVIDER"] = search_key

    if search_key != "ddgs":
        search_api_key = input(f"\n请输入 {search_info['name']} API Key：").strip()
        if not search_api_key:
            print("未输入搜索 API Key，将使用 DuckDuckGo 作为备选")
            env_vars["SEARCH_PROVIDER"] = "ddgs"
        else:
            env_vars["SEARCH_API_KEY"] = search_api_key
    else:
        print("DuckDuckGo 无需 API Key")

    # ── 写入 .env ──
    _write_env(env_vars)

    print(f"\n配置已保存到 {_ENV_PATH}")
    print("现在可以运行：python research.py \"你的查询\"")


def ensure_configured() -> bool:
    """检查是否已配置 LLM API key，未配置则提示"""
    if LLM_API_KEY:
        return True

    print("尚未配置 LLM API Key。")
    print("请运行: python research.py setup")
    return False


def _write_env(env_vars: dict[str, str]) -> None:
    """更新或追加 .env 文件中的变量"""
    env_lines: list[str] = []
    if _ENV_PATH.exists():
        env_lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()

    for var_name, var_value in env_vars.items():
        # 用双引号包裹值，防止特殊字符破坏 .env 格式
        quoted = f'"{var_value}"' if any(c in var_value for c in (' ', '#', '=', "'")) else var_value
        found = False
        for i, line in enumerate(env_lines):
            if line.startswith(f"{var_name}="):
                env_lines[i] = f"{var_name}={quoted}"
                found = True
                break
        if not found:
            env_lines.append(f"{var_name}={quoted}")

    _ENV_PATH.write_text("\n".join(env_lines) + "\n", encoding="utf-8")
