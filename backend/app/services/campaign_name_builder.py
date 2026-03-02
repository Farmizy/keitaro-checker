"""Campaign naming conventions for FB and Keitaro."""

from datetime import datetime

import zoneinfo

MOSCOW_TZ = zoneinfo.ZoneInfo("Europe/Moscow")

NICHE_SHORT = {
    "Диабет": "Диабет",
    "Гипертония": "Гипер",
    "Паразиты": "Паразиты",
    "Суставы": "Суставы",
    "Похудение": "Похуд",
}


def build_fb_campaign_name(
    niche: str,
    geo: str,
    product_name: str,
    angle: str,
    campaign_number: int,
    account_short: str,
    creative_version: str = "",
) -> str:
    """Build FB campaign name.

    Example: 02.03 v1 Диабет/PL/DiabetOver(LP)/Ewa Dąbrowska v6[ral]
    """
    today = datetime.now(MOSCOW_TZ).strftime("%d.%m")
    version_suffix = f" {creative_version}" if creative_version else ""
    return (
        f"{today} v{campaign_number} "
        f"{niche}/{geo}/{product_name}/"
        f"{angle}{version_suffix}[{account_short}]"
    )


def build_keitaro_campaign_name(
    niche: str,
    geo: str,
    product_name: str,
    domain: str,
    campaign_number: int,
    buyer_name: str,
    fb_account_id: str,
) -> str:
    """Build Keitaro campaign name.

    Example: raleksintsev/(02.03)/Гипер/1448769840010370/Cardiform/LT/https://enersync-vigor.info/ v2
    """
    today = datetime.now(MOSCOW_TZ).strftime("%d.%m")
    niche_short = NICHE_SHORT.get(niche, niche)
    clean_account_id = fb_account_id.replace("act_", "")
    return (
        f"{buyer_name}/({today})/{niche_short}/{clean_account_id}/"
        f"{product_name}/{geo}/https://{domain}/ v{campaign_number}"
    )
