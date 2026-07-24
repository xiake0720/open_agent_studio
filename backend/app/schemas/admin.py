from pydantic import BaseModel, Field, field_validator


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=32)
    password: str = Field(min_length=1, max_length=128)
    captcha_id: str | None = None
    captcha_code: str | None = Field(default=None, max_length=12)


class AdminUserUpdate(BaseModel):
    is_active: bool


class AdminModelCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=50)
    display_name: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=4096)
    api_key_env: str | None = Field(default=None, max_length=100)
    api_shape: str = Field(default="chat_completions", max_length=50)
    support_streaming: bool = True
    support_tools: bool = False
    support_image: bool = False
    enabled: bool = True
    extra_body_json: str | None = None

    @field_validator("provider", "display_name", "model_id", "base_url", "api_shape")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("api_key", "api_key_env", mode="before")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AdminModelUpdate(AdminModelCreate):
    pass


class AdminExceptionUpdate(BaseModel):
    resolved: bool
