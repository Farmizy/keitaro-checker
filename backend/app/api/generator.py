from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from loguru import logger

from app.core.auth import get_current_user
from app.schemas.generator import (
    AccountProfileCreate,
    AccountProfileResponse,
    AccountProfileUpdate,
    GenerateRequest,
)
from app.services.campaign_name_builder import (
    build_fb_campaign_name,
    build_keitaro_campaign_name,
)
from app.services.database_service import DatabaseService
from app.services.excel_generator import CampaignSpec, generate_fb_excel

router = APIRouter()


def get_db() -> DatabaseService:
    return DatabaseService()


@router.get("/offers")
async def list_offers(
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Get list of offers from Keitaro, filtered by user's group."""
    keitaro = request.app.state.keitaro
    # Auto-detect group by Keitaro login name
    groups = await keitaro.get_offer_groups()
    user_group = next(
        (g for g in groups if g["name"] == keitaro._login), None,
    )
    group_id = user_group["value"] if user_group else None
    return await keitaro.get_offers(group_id=group_id)


@router.get("/domains")
async def list_domains(
    request: Request,
    _user: dict = Depends(get_current_user),
):
    """Get list of domains from Keitaro."""
    keitaro = request.app.state.keitaro
    return await keitaro.get_domains()


@router.get("/pages/{account_id}")
async def list_pages(
    account_id: UUID,
    request: Request,
    _user: dict = Depends(get_current_user),
    db: DatabaseService = Depends(get_db),
):
    """Get Facebook Pages for an account from Panel API."""
    account = db.get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    panel_id = account.get("panel_account_id")
    if not panel_id:
        raise HTTPException(status_code=400, detail="Account has no panel_account_id")
    panel = request.app.state.panel
    pages = await panel.get_account_pages(panel_id)
    return [{"id": p.id, "name": p.name} for p in pages]


@router.get("/account-profiles", response_model=list[AccountProfileResponse])
async def list_account_profiles(
    _user: dict = Depends(get_current_user),
    db: DatabaseService = Depends(get_db),
):
    return db.get_account_profiles()


@router.post(
    "/account-profiles",
    response_model=AccountProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_account_profile(
    payload: AccountProfileCreate,
    _user: dict = Depends(get_current_user),
    db: DatabaseService = Depends(get_db),
):
    data = payload.model_dump()
    data["fb_account_id"] = str(data["fb_account_id"])
    return db.create_account_profile(data)


@router.put("/account-profiles/{profile_id}", response_model=AccountProfileResponse)
async def update_account_profile(
    profile_id: UUID,
    payload: AccountProfileUpdate,
    _user: dict = Depends(get_current_user),
    db: DatabaseService = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = db.update_account_profile(profile_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result


@router.post("/generate")
async def generate_campaigns(
    req: GenerateRequest,
    request: Request,
    _user: dict = Depends(get_current_user),
    db: DatabaseService = Depends(get_db),
):
    """Create Keitaro campaigns, then generate FB Ads Manager Excel."""
    keitaro = request.app.state.keitaro
    specs: list[CampaignSpec] = []
    keitaro_results: list[dict] = []

    for i, entry in enumerate(req.campaigns, 1):
        # Load account and profile
        account = db.get_account(entry.fb_account_id)
        if not account:
            raise HTTPException(
                status_code=404,
                detail=f"Account {entry.fb_account_id} not found",
            )

        profile = db.get_account_profile_by_account(entry.fb_account_id)
        if not profile:
            raise HTTPException(
                status_code=400,
                detail=f"No profile for account {account['name']}. Set up Page ID / Pixel ID first.",
            )

        account_short = account["name"][:3]
        buyer_name = account["name"]
        fb_account_id = account["account_id"]

        # 1. Build Keitaro campaign name
        keitaro_name = build_keitaro_campaign_name(
            niche=entry.niche,
            geo=entry.geo,
            product_name=entry.product_name,
            domain=entry.domain,
            campaign_number=i,
            buyer_name=buyer_name,
            fb_account_id=fb_account_id,
        )

        # 2. Create campaign in Keitaro → get alias
        keitaro_campaign = await keitaro.create_campaign(
            name=keitaro_name, domain=entry.domain,
            buyer_name=buyer_name,
        )
        keitaro_id = keitaro_campaign["id"]
        alias = keitaro_campaign.get("alias", "")
        logger.info(f"Created Keitaro campaign #{keitaro_id} alias={alias}")

        # 3. Create streams: Kloaka + ОСНОВНОЙ
        await keitaro.create_kloaka_stream(
            campaign_id=keitaro_id, geo=entry.geo,
        )
        if entry.offer_id:
            await keitaro.create_stream(
                campaign_id=keitaro_id,
                offer_ids=[entry.offer_id],
                countries=[entry.geo],
            )

        # 4. Build landing URL from alias
        landing_url = f"https://{entry.domain}/{alias}"

        # 5. Build URL tags
        url_tags = profile["url_tags_template"]
        url_tags = url_tags.replace("{keitaro_campaign_id}", str(keitaro_id))
        url_tags = url_tags.replace("{pixel_id}", profile["pixel_id"])
        url_tags = url_tags.replace("{buyer_name}", buyer_name)

        # 6. Build FB campaign name
        fb_name = build_fb_campaign_name(
            niche=entry.niche,
            geo=entry.geo,
            product_name=entry.product_name,
            angle=entry.angle,
            campaign_number=i,
            account_short=account_short,
            creative_version=entry.creative_version,
        )

        specs.append(CampaignSpec(
            campaign_name=fb_name,
            num_adsets=entry.num_adsets,
            geo=entry.geo,
            page_id=profile["page_id"],
            pixel_id=profile["pixel_id"],
            instagram_id=profile.get("instagram_id", ""),
            daily_budget=entry.daily_budget,
            landing_url=landing_url,
            custom_audiences=profile.get("custom_audiences", ""),
            url_tags=url_tags,
        ))

        keitaro_results.append({
            "keitaro_id": keitaro_id,
            "alias": alias,
            "landing_url": landing_url,
            "keitaro_name": keitaro_name,
            "fb_name": fb_name,
        })

    # 7. Generate Excel
    wb = generate_fb_excel(specs)
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="campaigns_{today}.xlsx"',
            "X-Keitaro-Results": str(keitaro_results),
        },
    )
