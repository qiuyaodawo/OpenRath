import json
import os
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from _chunk_print import example_chunk_print
from _openai_provider import provider_from_env
from pydantic import BaseModel, Field

import rath.flow as flow
from rath.flow.tool import FlowToolCall
from rath.session.session import Session

BIGMODEL_IMAGES_URL = "https://open.bigmodel.cn/api/paas/v4/images/generations"


class ImageGenInput(BaseModel):
    prompt: str = Field(
        description="Text prompt (see GLM-Image limits, max ~1000 chars)."
    )
    size: str = Field(
        default="1280x1280",
        description="Output size, e.g. 1280x1280, 1568x1056.",
    )


class ImageGenTool(FlowToolCall):
    @property
    def name(self) -> str:
        return "image_gen"

    @property
    def description(self) -> str | None:
        return (
            "Generate an image with Zhipu GLM-Image (glm-image). Returns parsed API JSON "
            "(image URL often under data[0].url). Needs ZHIPU_API_KEY or OPENAI_API_KEY."
        )

    @property
    def parameters(self) -> Mapping[str, Any]:
        return dict(ImageGenInput.model_json_schema())

    def __call__(
        self, session: Session, arguments: Mapping[str, Any]
    ) -> dict[str, Any]:
        data = dict(arguments or {})
        model = ImageGenInput.model_validate(data)
        prompt, size = model.prompt, model.size
        key = os.environ.get("ZHIPU_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("Set ZHIPU_API_KEY or OPENAI_API_KEY")

        body = json.dumps(
            {"model": "glm-image", "prompt": prompt, "size": size},
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            BIGMODEL_IMAGES_URL,
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
            raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc

        return json.loads(raw)


if __name__ == "__main__":
    agent = flow.Agent(
        system_prompt="You have an image_gen tool for Zhipu GLM-Image. "
        "When the user asks for an image, call image_gen with a concise prompt "
        "and optional size (default 1280x1280). The tool returns API JSON; "
        "mention the image URL from the response.",
        provider=replace(provider_from_env(), model="glm-5.1"),
        tools=[ImageGenTool()],
        chunk_print=example_chunk_print(),
    )
    user_session = Session.from_user_message(
        "Generate a simple cartoon cat on a sofa (no text in the image). "
        "Use image_gen once, then answer in one short sentence. "
        "Save in ./custom_tool_usage.png"
    ).to("local", spec="./")

    out_session = agent(user_session)
