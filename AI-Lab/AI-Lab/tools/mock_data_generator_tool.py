"""
mock_data_generator_tool.py - 模拟数据生成工具
============================================
供 Coder（程序员）使用，根据数据结构描述生成模拟数据。
支持多种数据类型、格式和生成策略，用于测试、演示和原型开发。

安全性审计:
  ✅ 仅生成数据，不执行用户代码
  ✅ 输入验证，防止恶意数据生成
  ✅ 输出限制，防止生成过大数据集
  ✅ 支持多种安全的数据格式
"""

import json
import random
import string
import datetime
from typing import Type, List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field

# 尝试导入 crewai，如果失败则提供本地替代
try:
    from crewai.tools import BaseTool
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    # 提供本地 BaseTool 替代
    class BaseTool:
        """本地 BaseTool 替代，用于在没有 crewai 的情况下运行"""
        name: str = ""
        description: str = ""
        args_schema: Type[BaseModel] = None

        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def _run(self, **kwargs) -> str:
            raise NotImplementedError("Subclasses must implement _run method")


class MockDataGeneratorInput(BaseModel):
    """MockDataGeneratorTool 的输入参数模型。"""
    data_schema: str = Field(
        ...,
        description=(
            "数据结构描述。可以是：\n"
            "1. JSON Schema 格式\n"
            "2. 简单的字段描述（如：'name:string, age:int, email:string'）\n"
            "3. Python字典结构描述\n"
            "4. 数据库表结构描述\n"
            "示例：{\"name\": \"string\", \"age\": \"integer\", \"email\": \"email\", \"active\": \"boolean\"}"
        )
    )
    data_count: int = Field(
        default=10,
        description="生成的数据记录数量。默认10条，最大1000条。",
        ge=1,
        le=1000
    )
    output_format: str = Field(
        default="json",
        description=(
            "输出格式。可选值：\n"
            "- 'json': JSON格式（默认）\n"
            "- 'csv': CSV格式\n"
            "- 'sql': SQL插入语句\n"
            "- 'python': Python列表/字典\n"
            "- 'yaml': YAML格式\n"
        )
    )
    generation_strategy: str = Field(
        default="random",
        description=(
            "数据生成策略。可选值：\n"
            "- 'random': 随机生成（默认）\n"
            "- 'sequential': 顺序生成\n"
            "- 'realistic': 真实数据模拟\n"
            "- 'edge_cases': 边界值测试\n"
            "- 'mixed': 混合策略\n"
        )
    )


class MockDataGeneratorTool(BaseTool):
    """模拟数据生成工具。

    根据数据结构描述生成模拟数据，支持多种数据类型、格式和生成策略。
    用于测试、演示、原型开发等场景。
    """

    name: str = "mock_data_generator"
    description: str = (
        "根据数据结构描述生成模拟数据。"
        "支持多种数据类型、格式和生成策略，用于测试、演示和原型开发。"
        "输出格式化的模拟数据，可直接用于测试或开发。"
    )
    args_schema: Type[BaseModel] = MockDataGeneratorInput

    # 预设数据池
    FIRST_NAMES = ["张伟", "王芳", "李娜", "刘洋", "陈静", "杨帆", "赵磊", "周涛", "吴明", "郑华",
                  "孙丽", "朱勇", "马强", "胡军", "林芳", "郭伟", "何静", "高飞", "罗敏", "梁超"]
    LAST_NAMES = ["张", "王", "李", "刘", "陈", "杨", "赵", "周", "吴", "郑",
                 "孙", "朱", "马", "胡", "林", "郭", "何", "高", "罗", "梁"]
    DOMAINS = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "163.com", "qq.com"]
    COMPANIES = ["科技有限公司", "信息技术公司", "软件开发公司", "电子商务公司", "咨询服务公司",
                "制造企业", "金融机构", "医疗机构", "教育机构", "零售企业"]
    CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆"]
    STREETS = ["中山路", "解放路", "人民路", "建设路", "文化路", "和平路", "光明路", "胜利路", "朝阳路", "东风路"]

    def _run(self, data_schema: str, data_count: int = 10,
            output_format: str = "json", generation_strategy: str = "random") -> str:
        """执行模拟数据生成。

        Args:
            data_schema: 数据结构描述
            data_count: 生成的数据记录数量
            output_format: 输出格式
            generation_strategy: 数据生成策略

        Returns:
            格式化的模拟数据
        """
        try:
            # 1. 解析数据结构
            schema_info = self._parse_data_schema(data_schema)

            # 2. 生成模拟数据
            mock_data = self._generate_mock_data(schema_info, data_count, generation_strategy)

            # 3. 格式化输出
            formatted_output = self._format_output(mock_data, schema_info, output_format)

            # 4. 生成完整报告
            return self._generate_report(data_schema, data_count, output_format,
                                        generation_strategy, schema_info, mock_data, formatted_output)

        except Exception as e:
            return f"❌ 模拟数据生成失败: {str(e)}"

    def _parse_data_schema(self, data_schema: str) -> Dict[str, Any]:
        """解析数据结构描述"""
        schema_info = {
            "fields": [],
            "field_types": {},
            "field_constraints": {},
            "parsed_successfully": False,
            "parse_method": "unknown",
        }

        try:
            # 尝试解析为JSON
            if data_schema.strip().startswith('{') and data_schema.strip().endswith('}'):
                try:
                    schema_dict = json.loads(data_schema)
                    schema_info["parse_method"] = "json"
                    schema_info["parsed_successfully"] = True

                    for field_name, field_type in schema_dict.items():
                        schema_info["fields"].append(field_name)
                        schema_info["field_types"][field_name] = str(field_type).lower()
                except json.JSONDecodeError:
                    # 如果不是有效JSON，尝试其他解析方法
                    pass

            # 如果JSON解析失败，尝试简单格式
            if not schema_info["parsed_successfully"]:
                schema_info["parse_method"] = "simple"
                # 尝试解析简单格式：field:type, field:type
                parts = [p.strip() for p in data_schema.split(',')]
                for part in parts:
                    if ':' in part:
                        field_parts = part.split(':', 1)
                        if len(field_parts) == 2:
                            field_name = field_parts[0].strip()
                            field_type = field_parts[1].strip().lower()
                            schema_info["fields"].append(field_name)
                            schema_info["field_types"][field_name] = field_type
                            schema_info["parsed_successfully"] = True

            # 如果还是失败，使用默认字段
            if not schema_info["parsed_successfully"]:
                schema_info["parse_method"] = "default"
                # 使用常见字段
                default_schema = {
                    "id": "integer",
                    "name": "string",
                    "age": "integer",
                    "email": "email",
                    "active": "boolean",
                    "created_at": "datetime",
                }
                for field_name, field_type in default_schema.items():
                    schema_info["fields"].append(field_name)
                    schema_info["field_types"][field_name] = field_type
                schema_info["parsed_successfully"] = True

        except Exception as e:
            # 解析失败时使用默认字段
            schema_info["parse_method"] = "error_fallback"
            default_schema = {
                "id": "integer",
                "name": "string",
                "age": "integer",
                "email": "email",
            }
            for field_name, field_type in default_schema.items():
                schema_info["fields"].append(field_name)
                schema_info["field_types"][field_name] = field_type

        return schema_info

    def _generate_mock_data(self, schema_info: Dict[str, Any], data_count: int,
                           generation_strategy: str) -> List[Dict[str, Any]]:
        """生成模拟数据"""
        mock_data = []

        for i in range(data_count):
            record = {}
            for field_name in schema_info["fields"]:
                field_type = schema_info["field_types"].get(field_name, "string")
                record[field_name] = self._generate_field_value(
                    field_name, field_type, i, data_count, generation_strategy
                )
            mock_data.append(record)

        return mock_data

    def _generate_field_value(self, field_name: str, field_type: str, index: int,
                             total_count: int, strategy: str) -> Any:
        """生成字段值"""
        field_name_lower = field_name.lower()

        # 根据字段名推测可能的类型
        if field_name_lower in ["id", "user_id", "customer_id", "order_id"]:
            return self._generate_id(index, strategy)
        elif field_name_lower in ["name", "username", "fullname", "display_name"]:
            return self._generate_name(index, strategy)
        elif field_name_lower in ["email", "email_address"]:
            return self._generate_email(index, strategy)
        elif field_name_lower in ["age"]:
            return self._generate_age(index, strategy)
        elif field_name_lower in ["phone", "phone_number", "mobile", "telephone"]:
            return self._generate_phone(index, strategy)
        elif field_name_lower in ["address", "street", "city", "country"]:
            return self._generate_address(index, strategy, field_name_lower)
        elif field_name_lower in ["price", "amount", "cost", "value", "salary"]:
            return self._generate_number(index, strategy, "decimal")
        elif field_name_lower in ["quantity", "count", "stock"]:
            return self._generate_number(index, strategy, "integer")
        elif field_name_lower in ["created_at", "updated_at", "timestamp", "date", "time"]:
            return self._generate_datetime(index, strategy)
        elif field_name_lower in ["active", "enabled", "status", "is_active", "is_valid"]:
            return self._generate_boolean(index, strategy)
        elif field_name_lower in ["description", "content", "text", "message"]:
            return self._generate_text(index, strategy)
        elif field_name_lower in ["category", "type", "genre", "classification"]:
            return self._generate_category(index, strategy)
        elif field_name_lower in ["rating", "score", "grade"]:
            return self._generate_rating(index, strategy)
        else:
            # 根据声明的类型生成
            return self._generate_by_type(field_type, index, total_count, strategy)

    def _generate_by_type(self, field_type: str, index: int, total_count: int,
                         strategy: str) -> Any:
        """根据类型生成值"""
        field_type_lower = field_type.lower()

        if field_type_lower in ["int", "integer", "number"]:
            return self._generate_number(index, strategy, "integer")
        elif field_type_lower in ["float", "decimal", "double", "real"]:
            return self._generate_number(index, strategy, "decimal")
        elif field_type_lower in ["str", "string", "text", "varchar"]:
            return self._generate_string(index, strategy)
        elif field_type_lower in ["bool", "boolean"]:
            return self._generate_boolean(index, strategy)
        elif field_type_lower in ["date", "datetime", "timestamp"]:
            return self._generate_datetime(index, strategy)
        elif field_type_lower in ["email"]:
            return self._generate_email(index, strategy)
        elif field_type_lower in ["phone", "tel"]:
            return self._generate_phone(index, strategy)
        elif field_type_lower in ["url", "uri", "link"]:
            return self._generate_url(index, strategy)
        elif field_type_lower in ["json", "array", "list"]:
            return self._generate_json(index, strategy)
        elif field_type_lower in ["choice", "enum", "select"]:
            return self._generate_choice(index, strategy)
        else:
            # 默认生成字符串
            return f"mock_value_{index}"

    def _generate_id(self, index: int, strategy: str) -> Union[int, str]:
        """生成ID"""
        if strategy == "sequential":
            return index + 1
        elif strategy == "edge_cases":
            return random.choice([1, 999999, 0, -1])
        else:
            return random.randint(1000, 999999)

    def _generate_name(self, index: int, strategy: str) -> str:
        """生成姓名"""
        if strategy == "sequential":
            return f"测试用户{index+1}"
        elif strategy == "realistic":
            first_name = random.choice(self.FIRST_NAMES)
            last_name = random.choice(self.LAST_NAMES)
            return f"{last_name}{first_name}"
        elif strategy == "edge_cases":
            return random.choice(["", "A" * 50, "中文名字测试", "Name With Spaces"])
        else:
            return f"User{random.randint(1, 1000)}"

    def _generate_email(self, index: int, strategy: str) -> str:
        """生成邮箱"""
        if strategy == "sequential":
            return f"user{index+1}@example.com"
        elif strategy == "realistic":
            name = self._generate_name(index, "random").lower().replace(" ", ".")
            domain = random.choice(self.DOMAINS)
            return f"{name}@{domain}"
        elif strategy == "edge_cases":
            return random.choice(["", "invalid-email", "user@", "@domain.com", "a" * 100 + "@test.com"])
        else:
            return f"test{random.randint(1, 1000)}@example.com"

    def _generate_age(self, index: int, strategy: str) -> int:
        """生成年龄"""
        if strategy == "sequential":
            return (index % 80) + 18
        elif strategy == "realistic":
            return random.randint(18, 80)
        elif strategy == "edge_cases":
            return random.choice([0, 1, 17, 18, 65, 120, 150])
        else:
            return random.randint(18, 60)

    def _generate_phone(self, index: int, strategy: str) -> str:
        """生成电话号码"""
        if strategy == "sequential":
            return f"138001380{index:02d}"
        elif strategy == "realistic":
            prefix = random.choice(["138", "139", "150", "151", "152", "186", "187", "188"])
            return f"{prefix}{random.randint(1000, 9999)}{random.randint(1000, 9999)}"
        elif strategy == "edge_cases":
            return random.choice(["", "123", "1234567890123456", "abc-def-ghij"])
        else:
            return f"1{random.randint(3000000000, 3999999999)}"

    def _generate_address(self, index: int, strategy: str, field_name: str) -> str:
        """生成地址"""
        if field_name == "city":
            if strategy == "sequential":
                return self.CITIES[index % len(self.CITIES)]
            else:
                return random.choice(self.CITIES)
        elif field_name == "street":
            if strategy == "sequential":
                return f"{self.STREETS[index % len(self.STREETS)]}{random.randint(1, 999)}号"
            else:
                return f"{random.choice(self.STREETS)}{random.randint(1, 999)}号"
        else:
            city = random.choice(self.CITIES)
            street = random.choice(self.STREETS)
            return f"{city}市{street}{random.randint(1, 999)}号"

    def _generate_number(self, index: int, strategy: str, number_type: str) -> Union[int, float]:
        """生成数字"""
        if strategy == "sequential":
            value = index + 1
        elif strategy == "realistic":
            if number_type == "integer":
                value = random.randint(1, 1000)
            else:
                value = round(random.uniform(1.0, 1000.0), 2)
        elif strategy == "edge_cases":
            return random.choice([0, -1, 999999, 0.0, -999.99])
        else:
            if number_type == "integer":
                value = random.randint(1, 1000)
            else:
                value = round(random.uniform(1.0, 1000.0), 2)

        if number_type == "decimal":
            return float(value)
        return value

    def _generate_datetime(self, index: int, strategy: str) -> str:
        """生成日期时间"""
        if strategy == "sequential":
            base_date = datetime.datetime.now() - datetime.timedelta(days=index)
            return base_date.strftime("%Y-%m-%d %H:%M:%S")
        elif strategy == "realistic":
            days_ago = random.randint(0, 365 * 5)
            random_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
            return random_date.strftime("%Y-%m-%d %H:%M:%S")
        elif strategy == "edge_cases":
            return random.choice(["", "2020-02-30", "9999-12-31", "1970-01-01"])
        else:
            days_ago = random.randint(0, 365)
            random_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
            return random_date.strftime("%Y-%m-%d %H:%M:%S")

    def _generate_boolean(self, index: int, strategy: str) -> bool:
        """生成布尔值"""
        if strategy == "sequential":
            return index % 2 == 0
        elif strategy == "realistic":
            return random.choice([True, False])
        elif strategy == "edge_cases":
            return random.choice([True, False])
        else:
            return random.choice([True, False])

    def _generate_text(self, index: int, strategy: str) -> str:
        """生成文本"""
        if strategy == "sequential":
            return f"这是第{index+1}条测试文本内容。"
        elif strategy == "realistic":
            texts = [
                "这是一个产品描述，用于测试数据生成功能。",
                "用户评论内容，表达对产品的看法和体验。",
                "项目说明文档，描述项目目标和实施计划。",
                "技术支持请求，描述遇到的问题和期望的解决方案。",
                "市场分析报告，包含行业趋势和竞争对手分析。"
            ]
            return random.choice(texts)
        elif strategy == "edge_cases":
            return random.choice(["", "A" * 500, "包含\n换行符\n的文本", "特殊字符!@#$%^&*()"])
        else:
            return f"随机文本{random.randint(1, 1000)}"

    def _generate_string(self, index: int, strategy: str) -> str:
        """生成字符串"""
        if strategy == "sequential":
            return f"string_{index+1}"
        elif strategy == "realistic":
            prefixes = ["prod", "test", "dev", "uat", "pre"]
            suffixes = ["item", "data", "record", "entry", "value"]
            return f"{random.choice(prefixes)}_{random.choice(suffixes)}_{random.randint(1, 100)}"
        elif strategy == "edge_cases":
            return random.choice(["", "a", "A" * 255, "中文测试", "with spaces"])
        else:
            length = random.randint(5, 20)
            return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    def _generate_url(self, index: int, strategy: str) -> str:
        """生成URL"""
        if strategy == "sequential":
            return f"https://example.com/item/{index+1}"
        else:
            domains = ["example.com", "test.org", "mock.dev", "demo.net"]
            paths = ["page", "item", "product", "article", "post"]
            return f"https://{random.choice(domains)}/{random.choice(paths)}/{random.randint(1, 1000)}"

    def _generate_json(self, index: int, strategy: str) -> str:
        """生成JSON"""
        if strategy == "sequential":
            return json.dumps({"id": index+1, "name": f"item_{index+1}"})
        else:
            return json.dumps({
                "id": random.randint(1, 1000),
                "name": random.choice(["item", "product", "service"]),
                "value": random.randint(1, 100)
            })

    def _generate_category(self, index: int, strategy: str) -> str:
        """生成分类"""
        categories = ["电子产品", "服装", "食品", "图书", "家居", "运动", "美妆", "汽车", "金融", "医疗"]
        if strategy == "sequential":
            return categories[index % len(categories)]
        else:
            return random.choice(categories)

    def _generate_rating(self, index: int, strategy: str) -> Union[int, float]:
        """生成评分"""
        if strategy == "sequential":
            return (index % 5) + 1
        elif strategy == "realistic":
            return round(random.uniform(1.0, 5.0), 1)
        elif strategy == "edge_cases":
            return random.choice([0, 1, 5, 10, -1])
        else:
            return random.randint(1, 5)

    def _generate_choice(self, index: int, strategy: str) -> str:
        """生成选择值"""
        choices = ["option_a", "option_b", "option_c", "option_d", "option_e"]
        if strategy == "sequential":
            return choices[index % len(choices)]
        else:
            return random.choice(choices)

    def _format_output(self, mock_data: List[Dict[str, Any]], schema_info: Dict[str, Any],
                      output_format: str) -> str:
        """格式化输出"""
        if output_format == "json":
            return json.dumps(mock_data, ensure_ascii=False, indent=2)
        elif output_format == "csv":
            return self._format_as_csv(mock_data, schema_info)
        elif output_format == "sql":
            return self._format_as_sql(mock_data, schema_info)
        elif output_format == "python":
            return self._format_as_python(mock_data)
        elif output_format == "yaml":
            return self._format_as_yaml(mock_data)
        else:
            return json.dumps(mock_data, ensure_ascii=False, indent=2)

    def _format_as_csv(self, mock_data: List[Dict[str, Any]], schema_info: Dict[str, Any]) -> str:
        """格式化为CSV"""
        if not mock_data:
            return ""

        # 获取字段名
        fields = schema_info["fields"]

        # 生成CSV头部
        csv_lines = [','.join(fields)]

        # 生成数据行
        for record in mock_data:
            row = []
            for field in fields:
                value = record.get(field, "")
                # 处理特殊字符
                if isinstance(value, str):
                    value = value.replace('"', '""')
                    if ',' in value or '"' in value or '\n' in value:
                        value = f'"{value}"'
                row.append(str(value))
            csv_lines.append(','.join(row))

        return '\n'.join(csv_lines)

    def _format_as_sql(self, mock_data: List[Dict[str, Any]], schema_info: Dict[str, Any]) -> str:
        """格式化为SQL插入语句"""
        if not mock_data:
            return ""

        table_name = "mock_data"
        fields = schema_info["fields"]

        sql_lines = []
        for i, record in enumerate(mock_data):
            values = []
            for field in fields:
                value = record.get(field, "")
                if isinstance(value, (int, float)):
                    values.append(str(value))
                elif value is None:
                    values.append("NULL")
                else:
                    # 转义单引号
                    value_str = str(value).replace("'", "''")
                    values.append(f"'{value_str}'")

            sql = f"INSERT INTO {table_name} ({', '.join(fields)}) VALUES ({', '.join(values)});"
            sql_lines.append(sql)

        return '\n'.join(sql_lines)

    def _format_as_python(self, mock_data: List[Dict[str, Any]]) -> str:
        """格式化为Python代码"""
        return f"mock_data = {repr(mock_data)}"

    def _format_as_yaml(self, mock_data: List[Dict[str, Any]]) -> str:
        """格式化为YAML"""
        try:
            import yaml
            return yaml.dump(mock_data, allow_unicode=True, default_flow_style=False)
        except ImportError:
            # 如果yaml不可用，使用简单格式
            yaml_lines = []
            for record in mock_data:
                yaml_lines.append("-")
                for key, value in record.items():
                    yaml_lines.append(f"  {key}: {repr(value)}")
            return '\n'.join(yaml_lines)

    def _generate_report(self, data_schema: str, data_count: int, output_format: str,
                        generation_strategy: str, schema_info: Dict[str, Any],
                        mock_data: List[Dict[str, Any]], formatted_output: str) -> str:
        """生成完整报告"""
        report = f"""# 模拟数据生成报告

## 生成配置
- **数据结构描述**: {data_schema[:200]}{'...' if len(data_schema) > 200 else ''}
- **数据记录数量**: {data_count}
- **输出格式**: {output_format}
- **生成策略**: {generation_strategy}
- **解析方法**: {schema_info['parse_method']}

## 数据结构分析
- **字段数量**: {len(schema_info['fields'])}
- **字段列表**: {', '.join(schema_info['fields'][:10])}{'...' if len(schema_info['fields']) > 10 else ''}
- **字段类型**:
"""

        for field in schema_info["fields"][:10]:  # 最多显示10个字段
            field_type = schema_info["field_types"].get(field, "unknown")
            report += f"  - `{field}`: {field_type}\n"

        if len(schema_info["fields"]) > 10:
            report += f"  ... 还有 {len(schema_info['fields']) - 10} 个字段\n"

        report += f"""
## 数据预览（前3条记录）
"""

        for i, record in enumerate(mock_data[:3]):
            report += f"### 记录 {i+1}\n```json\n{json.dumps(record, ensure_ascii=False, indent=2)}\n```\n"

        report += f"""
## 生成的数据统计
- **总记录数**: {len(mock_data)}
- **数据类型分布**:
"""

        # 统计字段类型分布
        type_counts = {}
        for field_type in schema_info["field_types"].values():
            type_counts[field_type] = type_counts.get(field_type, 0) + 1

        for field_type, count in sorted(type_counts.items()):
            report += f"  - `{field_type}`: {count} 个字段\n"

        report += f"""
## 生成的模拟数据（{output_format.upper()}格式）
```{output_format if output_format != 'python' else 'python'}
{formatted_output[:2000]}{'...' if len(formatted_output) > 2000 else ''}
```

## 使用说明
### 1. 直接使用
生成的{output_format.upper()}格式数据可直接用于：
- 单元测试和集成测试
- 数据库填充和迁移
- API开发和测试
- 前端界面原型开发

### 2. 自定义修改
如需自定义数据，可以：
1. 修改数据结构描述中的字段类型
2. 调整生成策略获得不同风格的数据
3. 修改输出格式适配不同使用场景

### 3. 扩展功能
此工具支持：
- **多种数据类型**: 字符串、数字、日期、布尔值、JSON等
- **多种输出格式**: JSON、CSV、SQL、Python、YAML
- **多种生成策略**: 随机、顺序、真实模拟、边界值测试
- **智能字段识别**: 根据字段名自动选择合适的数据类型

## 结构化数据（JSON）
```json
{json.dumps({
    "config": {
        "data_schema_preview": data_schema[:100],
        "data_count": data_count,
        "output_format": output_format,
        "generation_strategy": generation_strategy
    },
    "schema_info": {
        "field_count": len(schema_info["fields"]),
        "fields": schema_info["fields"],
        "field_types": schema_info["field_types"]
    },
    "data_sample": mock_data[:3] if mock_data else []
}, ensure_ascii=False, indent=2)}
```
"""

        return report


# 示例用法
if __name__ == "__main__":
    # 测试工具
    tool = MockDataGeneratorTool()

    # 测试1: JSON Schema格式
    test_schema = '''
    {
        "id": "integer",
        "name": "string",
        "email": "email",
        "age": "integer",
        "active": "boolean",
        "created_at": "datetime"
    }
    '''

    result1 = tool._run(
        data_schema=test_schema,
        data_count=5,
        output_format="json",
        generation_strategy="realistic"
    )

    print("测试1结果:")
    print(result1[:1500] + "..." if len(result1) > 1500 else result1)
