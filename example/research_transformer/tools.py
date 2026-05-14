"""Optional FlowToolCall for research-background images (Zhipu BigModel, OpenAI-compatible URL)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from typing import Any, cast

from pydantic import BaseModel, Field

from rath.flow.tool import FlowToolCall
from rath.session.session import Session

_BIGMODEL_IMAGES_URL = "https://open.bigmodel.cn/api/paas/v4/images/generations"


class BackgroundImageInput(BaseModel):
    prompt: str = Field(
        description="Short visual description for a research-style background."
    )
    size: str = Field(
        default="1280x720",
        description="Output size, e.g. 1280x720.",
    )


class BackgroundImageTool(FlowToolCall):
    """Generate a background figure via Zhipu GLM-Image (optional; keys from env)."""

    @property
    def name(self) -> str:
        return "background_image"

    @property
    def description(self) -> str | None:
        return (
            "Optional: generate a research-style background image (BigModel glm-image). "
            "Returns API JSON (URL often under data[0].url). "
            "Needs ZHIPU_API_KEY or OPENAI_API_KEY."
        )

    @property
    def parameters(self) -> Mapping[str, Any]:
        return dict(BackgroundImageInput.model_json_schema())

    def __call__(
        self, session: Session, arguments: Mapping[str, Any]
    ) -> dict[str, Any]:
        del session
        data = dict(arguments or {})
        model = BackgroundImageInput.model_validate(data)
        key = os.environ.get("ZHIPU_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not key:
            return {
                "ok": False,
                "skipped": True,
                "error": "Set ZHIPU_API_KEY or OPENAI_API_KEY to enable background_image",
            }

        body = json.dumps(
            {"model": "glm-image", "prompt": model.prompt, "size": model.size},
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            _BIGMODEL_IMAGES_URL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:2000]
            return {"ok": False, "http_status": exc.code, "detail": detail}

        return cast(dict[str, Any], json.loads(raw))


def optional_image_tools(*, skip_images: bool) -> list[FlowToolCall] | None:
    """Return ``[BackgroundImageTool]`` unless ``skip_images``."""

    if skip_images:
        return None
    return [BackgroundImageTool()]
