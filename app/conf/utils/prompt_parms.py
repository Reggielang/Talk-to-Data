import datetime
from dateutil.relativedelta import relativedelta

# 时间处理函数
def create_date_function(base_date=None):
    """创建日期函数"""
    
    def _parse_date(date_input):
        """解析日期输入"""
        if date_input is None:
            return datetime.datetime.now()
        elif isinstance(date_input, datetime.datetime):
            return date_input
        elif isinstance(date_input, datetime.date):
            return datetime.datetime.combine(date_input, datetime.time())
        elif isinstance(date_input, (int, float)):
            return datetime.datetime.fromtimestamp(date_input)
        elif isinstance(date_input, str):
            for fmt in ['%Y-%m-%d', '%Y%m%d', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S']:
                try:
                    return datetime.datetime.strptime(date_input, fmt)
                except ValueError:
                    continue
            raise ValueError(f"无法解析日期字符串: {date_input}")
        else:
            raise TypeError(f"不支持的日期类型: {type(date_input)}")
    
    parsed_date = _parse_date(base_date)
    
    def date(format_str, modifier=None, modifier2=None):
        # 处理 Y-m 格式
        if format_str == "Y-m":
            if modifier == "Month-1":
                last_month = parsed_date - relativedelta(months=1)
                return last_month.strftime("%Y-%m")
            elif modifier == "Quarter-1":
                # 上一季度
                quarter = (parsed_date.month - 1) // 3 + 1
                if quarter == 1:
                    prev_year = parsed_date.year - 1
                    prev_quarter = 4
                else:
                    prev_year = parsed_date.year
                    prev_quarter = quarter - 1
                
                if modifier2 == "QuarterBegin":
                    prev_month = (prev_quarter - 1) * 3 + 1
                    return f"{prev_year}-{prev_month:02d}"
                elif modifier2 == "QuarterEnd":
                    prev_month = prev_quarter * 3
                    return f"{prev_year}-{prev_month:02d}"
            else:
                return parsed_date.strftime("%Y-%m")
        
        # 处理 Y-m-d 格式
        elif format_str == "Y-m-d":
            if not modifier:
                return parsed_date.strftime("%Y-%m-%d")
            elif modifier == "Day-29":
                date_29 = parsed_date - datetime.timedelta(days=29)
                return date_29.strftime("%Y-%m-%d")
            elif modifier == "Day-6":
                date_6 = parsed_date - datetime.timedelta(days=6)
                return date_6.strftime("%Y-%m-%d")
            elif modifier == "WeekBegin":
                week_start = parsed_date - datetime.timedelta(days=parsed_date.weekday())
                return week_start.strftime("%Y-%m-%d")
            elif modifier == "WeekEnd":
                week_start = parsed_date - datetime.timedelta(days=parsed_date.weekday())
                week_end = week_start + datetime.timedelta(days=6)
                return week_end.strftime("%Y-%m-%d")
            elif modifier == "Week-1":
                if modifier2 == "WeekBegin":
                    week_start = parsed_date - datetime.timedelta(days=parsed_date.weekday())
                    last_week_start = week_start - datetime.timedelta(days=7)
                    return last_week_start.strftime("%Y-%m-%d")
                elif modifier2 == "WeekEnd":
                    week_start = parsed_date - datetime.timedelta(days=parsed_date.weekday())
                    last_week_start = week_start - datetime.timedelta(days=7)
                    last_week_end = last_week_start + datetime.timedelta(days=6)
                    return last_week_end.strftime("%Y-%m-%d")
        
        # 年份
        elif format_str == "Y":
            return str(parsed_date.year)
        
        # 月份
        elif format_str == "m":
            if modifier == "QuarterBegin":
                quarter = (parsed_date.month - 1) // 3 + 1
                quarter_start_month = (quarter - 1) * 3 + 1
                return f"{quarter_start_month:02d}"
            elif modifier == "QuarterEnd":
                quarter = (parsed_date.month - 1) // 3 + 1
                quarter_end_month = quarter * 3
                return f"{quarter_end_month:02d}"
            else:
                return f"{parsed_date.month:02d}"
        
        # 季度
        elif format_str == "q":
            if modifier == "Quarter-1" and modifier2 == "QuarterBegin":
                quarter = (parsed_date.month - 1) // 3 + 1
                if quarter == 1:
                    return "4"
                else:
                    return str(quarter - 1)
            else:
                return str((parsed_date.month - 1) // 3 + 1)
        
        return ""
    
    return date