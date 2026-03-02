from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AccountProfileCreate(BaseModel):
    fb_account_id: UUID
    page_id: str = Field(..., min_length=1)
    pixel_id: str = Field(..., min_length=1)
    instagram_id: str = ""
    default_geo: str = ""
    default_budget: float = 30
    custom_audiences: str = ""
    url_tags_template: str = (
        "campaign_id={keitaro_campaign_id}&ad_id={{ad.id}}"
        "&fbpx={pixel_id}&buyer_name={buyer_name}&account_id={{account.id}}"
    )


class AccountProfileUpdate(BaseModel):
    page_id: Optional[str] = None
    pixel_id: Optional[str] = None
    instagram_id: Optional[str] = None
    default_geo: Optional[str] = None
    default_budget: Optional[float] = None
    custom_audiences: Optional[str] = None
    url_tags_template: Optional[str] = None


class AccountProfileResponse(BaseModel):
    id: UUID
    fb_account_id: UUID
    page_id: str
    pixel_id: str
    instagram_id: str
    default_geo: str
    default_budget: float
    custom_audiences: str
    url_tags_template: str
    default_language: str
    additional_languages: list[str]
    created_at: datetime
    updated_at: datetime


class CampaignEntryRequest(BaseModel):
    niche: str
    geo: str
    product_name: str
    angle: str
    domain: str
    fb_account_id: UUID
    offer_id: Optional[int] = None
    num_adsets: int = Field(default=2, ge=1, le=5)
    daily_budget: float = 30
    creative_version: str = ""


class GenerateRequest(BaseModel):
    campaigns: list[CampaignEntryRequest] = Field(..., min_length=1)
