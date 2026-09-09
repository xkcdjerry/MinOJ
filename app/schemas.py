"""Pydantic 请求/响应模型。"""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class Sample(BaseModel):
    input: str
    output: str


class TestCase(BaseModel):
    input: str
    output: str


class ProblemModel(BaseModel):
    """题目配置。必填字段缺失/类型错误由 Pydantic 校验，统一映射为 400。

    time_limit / memory_limit 使用 None 表示"未设置"，以便评测时按
    "题目配置 -> 语言配置 -> 系统默认值" 的顺序逐项确定。
    """

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_description: str = Field(min_length=1)
    output_description: str = Field(min_length=1)
    samples: List[Sample]
    constraints: str = Field(min_length=1)
    testcases: List[TestCase]
    hint: str = ""
    source: str = ""
    tags: List[str] = Field(default_factory=list)
    time_limit: Optional[float] = None
    memory_limit: Optional[int] = None
    author: str = ""
    difficulty: str = ""
    public_cases: bool = False

    @field_validator("testcases")
    @classmethod
    def _testcases_nonempty(cls, v):
        if not v:
            raise ValueError("testcases must not be empty")
        return v

    @field_validator("time_limit")
    @classmethod
    def _time_limit_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("time_limit must be positive")
        return v

    @field_validator("memory_limit")
    @classmethod
    def _memory_limit_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("memory_limit must be positive")
        return v


class LanguageModel(BaseModel):
    name: str = Field(min_length=1)
    file_ext: str = Field(min_length=1)
    compile_cmd: Optional[str] = None
    run_cmd: str = Field(min_length=1)
    time_limit: float = 3.0
    memory_limit: int = 128


class LoginModel(BaseModel):
    username: str
    password: str


class RegisterModel(BaseModel):
    username: str
    password: str


class RoleModel(BaseModel):
    role: str


class SubmissionCreate(BaseModel):
    problem_id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    code: str = Field(min_length=1)


class LogVisibilityModel(BaseModel):
    public_cases: Optional[bool] = False


class AIConfigModel(BaseModel):
    provider_url: str = Field(min_length=1)
    model: str = Field(min_length=1)
    api_key: str = Field(min_length=1)
    input_price: float = 0.0
    output_price: float = 0.0
    price_unit: int = 1000000


class AITaskCreate(BaseModel):
    requirement: str = Field(min_length=1)
    problem_id: Optional[str] = None
    inplace: bool = False
