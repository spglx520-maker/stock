#!/usr/bin/env python3
"""
每日上证指数数据采集器
- 使用新浪财经免费接口
- 自动校验数据有效性
- 追加记录到 CSV 和 JSON
"""

import csv
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

# ========== 配置 ==========
STOCK_CODE = "sh000001"          # 上证指数
STOCK_NAME = "上证指数"
API_URL = f"https://hq.sinajs.cn/list={STOCK_CODE}"
RETRY_TIMES = 3                  # 失败重试次数
RETRY_DELAY = 5                  # 重试间隔（秒）
CSV_FILE = "records.csv"
JSON_FILE = "records.json"

# 中国时区
CHINA_TZ = timezone(timedelta(hours=8))

def get_china_now():
    """获取当前北京时间"""
    return datetime.now().astimezone(CHINA_TZ)

def is_trading_day():
    """
    判断今天是不是A股交易日（简单判断）
    注意：这只是一个近似判断，精确的交易日历需要参考交易所公告
    """
    now = get_china_now()
    weekday = now.weekday()  # 0=周一, 6=周日
    
    # 周末不开盘
    if weekday >= 5:
        return False
    
    # 这里可以扩展：判断法定节假日
    # 更精确的做法：维护一个交易日历文件或调用交易日历API
    
    return True

def fetch_stock_data():
    """从新浪财经获取股票数据（带重试）"""
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    
    last_error = None
    for attempt in range(1, RETRY_TIMES + 1):
        try:
            req = urllib.request.Request(API_URL, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("gbk")
            
            # 解析数据
            content = raw.split('"')[1]
            parts = content.split(',')
            
            # 数据校验：必须包含至少32个字段
            if len(parts) < 32:
                raise ValueError(f"字段数不足: {len(parts)}")
            
            # 校验关键字段是否为有效数值
            name = parts[0].strip()
            current = parts[3].strip()
            
            if not name:
                raise ValueError("指数名称为空")
            
            if not current or current == "0":
                raise ValueError(f"当前价为无效值: {current}")
            
            # 解析成功
            return {
                "name": name,
                "open": parts[1].strip(),
                "last_close": parts[2].strip(),
                "current": current,
                "high": parts[4].strip(),
                "low": parts[5].strip(),
                "volume": parts[8].strip(),
                "amount": parts[9].strip(),
                "date": parts[30].strip(),
                "time": parts[31].strip()
            }
            
        except Exception as e:
            last_error = e
            print(f"⚠️ 第{attempt}次尝试失败: {e}")
            if attempt < RETRY_TIMES:
                import time
                time.sleep(RETRY_DELAY)
    
    # 所有重试都失败
    raise Exception(f"获取数据失败（已重试{RETRY_TIMES}次）: {last_error}")

def calc_change(current, last_close):
    """计算涨跌幅"""
    cur = float(current)
    lc = float(last_close)
    change_val = round(cur - lc, 2)
    change_pct = round((cur - lc) / lc * 100, 2)
    return change_val, change_pct

def save_to_csv(record, filepath):
    """追加写入CSV"""
    file_exists = os.path.isfile(filepath)
    fieldnames = list(record.keys())
    
    with open(filepath, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(record)
    
    print(f"✅ CSV已保存 ({os.path.getsize(filepath)} bytes)")

def save_to_json(record, filepath):
    """追加写入JSON"""
    records = []
    if os.path.isfile(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    records = json.loads(content)
        except (json.JSONDecodeError, Exception) as e:
            print(f"⚠️ JSON文件读取失败，将重建: {e}")
            records = []
    
    records.append(record)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    
    print(f"✅ JSON已保存 (共{len(records)}条记录)")

def main():
    now = get_china_now()
    print(f"🕐 北京时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📆 星期{now.weekday() + 1}")
    
    # 判断是否交易日（如果是节假日，仍尝试获取数据，但结果可能无效）
    if not is_trading_day():
        print("📅 今天是非交易日（周末），跳过数据采集")
        # 非交易日不一定没数据，有些接口会返回最近交易日的收盘数据
        # 所以仍尝试获取，但标记一下
        print("🔍 仍尝试获取最近交易日数据...")
    
    print(f"\n📡 正在获取 {STOCK_NAME} 数据...")
    print(f"   URL: {API_URL}")
    
    try:
        data = fetch_stock_data()
        change_val, change_pct = calc_change(data["current"], data["last_close"])
        
        # 构建记录
        record = {
            "日期": data["date"],
            "时间": data["time"],
            "指数名称": data["name"],
            "开盘价": data["open"],
            "昨收价": data["last_close"],
            "当前价": data["current"],
            "最高价": data["high"],
            "最低价": data["low"],
            "涨跌额": str(change_val),
            "涨跌幅%": str(change_pct),
            "成交量(手)": data["volume"],
            "成交额(元)": data["amount"],
            "记录时间": now.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # 打印结果
        print(f"\n📊 {data['name']}")
        print(f"📅 日期: {data['date']}  时间: {data['time']}")
        print(f"💰 当前价: {data['current']}")
        print(f"📈 涨跌额: {change_val:+.2f}  |  涨跌幅: {change_pct:+.2f}%")
        print(f"🔺 最高: {data['high']}  🔻 最低: {data['low']}")
        print(f"📊 成交量: {int(data['volume']):,} 手")
        print(f"💰 成交额: {int(data['amount']):,} 元")
        
        # 保存到文件
        save_to_csv(record, CSV_FILE)
        save_to_json(record, JSON_FILE)
        
        print(f"\n🎉 记录完成！")
        
    except Exception as e:
        print(f"\n❌ 采集失败: {e}")
        print("💡 可能原因：网络问题、非交易时间、接口变更")
        sys.exit(1)

if __name__ == "__main__":
    main()
