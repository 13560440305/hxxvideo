from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500, description="视频主题")
    niche: str = Field(default="general", description="内容模板名称")
    duration: int = Field(default=180, ge=10, le=600, description="目标时长（秒）")
    fmt: str = Field(default="youtube", pattern="^(youtube|shorts)$", description="视频格式")
    resolution: Optional[str] = Field(default=None, description="分辨率 720p/1080p/short 或 WxH")
    bg_music: Optional[str] = Field(default=None, description="背景音乐路径")
    skip_video: bool = Field(default=False, description="跳过视频合成")


class ProjectResponse(BaseModel):
    id: int
    topic: str
    niche: str
    duration: int
    format: str
    status: str
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    script_json: Optional[dict] = None
    storyboard_json: Optional[dict] = None
    scenes: Optional[list[dict]] = None


class StatusResponse(BaseModel):
    id: int
    status: str
    updated_at: str


class ScriptUpdateRequest(BaseModel):
    scenes: list[dict] = Field(..., description="编辑后的场景列表")


class NicheItem(BaseModel):
    name: str
    description: str
    file: str
