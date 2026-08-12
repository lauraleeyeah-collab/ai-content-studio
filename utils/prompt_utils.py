"""
轻量级Prompt模板渲染工具。

之所以不用Python原生str.format(),是因为Prompt里大量出现JSON输出格式示例,
里面写满了单花括号 { }。如果用.format(),Python会把JSON示例里的花括号也当成
占位符尝试替换,导致报错或结果错乱。

这里改用 {{变量名}} 双花括号的占位符语法,正则只替换双花括号包裹的内容,
不会影响JSON示例里的单花括号,两者可以在同一个模板字符串里共存。
"""
import re

_PLACEHOLDER_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def render(template: str, **kwargs) -> str:
    """
    把template里所有{{key}}替换成kwargs[key]的字符串形式。
    如果模板里用到了未提供的变量,直接报错,避免悄悄漏填导致Prompt不完整。
    """

    def _replace(match: "re.Match") -> str:
        key = match.group(1)
        if key not in kwargs:
            raise KeyError(f"Prompt模板缺少变量:{key}")
        return str(kwargs[key])

    return _PLACEHOLDER_PATTERN.sub(_replace, template)
