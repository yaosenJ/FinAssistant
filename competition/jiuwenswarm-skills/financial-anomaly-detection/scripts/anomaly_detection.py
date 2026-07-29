#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
财务异常检测脚本 - 供 financial-anomaly-detection Skill 调用
"""
import sys
import os
import json
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINASSISTANT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(SCRIPT_DIR))))
sys.path.insert(0, FINASSISTANT_DIR)
from tools.financial_anomaly import detect_anomalies


def run_analysis(ts_code, report_date=None):
    result = detect_anomalies(ts_code, report_date)
    return result


def format_output(result):
    """detect_anomalies 返回的是已格式化的字符串，直接返回"""
    if isinstance(result, str):
        return result
    return str(result)


def parse_alerts(result):
    """从格式化结果中提取结构化数据"""
    if not isinstance(result, str):
        return {'raw': str(result)}

    alerts = []
    lines = result.split('\n')
    current_alert = None

    for line in lines:
        line = line.strip()
        if line.startswith('!!') or line.startswith('! '):
            if current_alert:
                alerts.append(current_alert)
            # 解析 [severity] type
            parts = line[2:].strip()
            if parts.startswith('['):
                bracket_end = parts.index(']')
                severity = parts[1:bracket_end]
                alert_type = parts[bracket_end+1:].strip()
            else:
                severity = 'UNKNOWN'
                alert_type = parts
            current_alert = {'severity': severity, 'type': alert_type, 'detail': '', 'explanation': ''}
        elif current_alert and line.startswith('数据:'):
            current_alert['detail'] = line[3:].strip()
        elif current_alert and line.startswith('说明:'):
            current_alert['explanation'] = line[3:].strip()

    if current_alert:
        alerts.append(current_alert)

    return {
        'raw': result,
        'alerts': alerts,
        'high_count': sum(1 for a in alerts if a['severity'] == 'HIGH'),
        'medium_count': sum(1 for a in alerts if a['severity'] == 'MEDIUM'),
        'risk_level': 'HIGH' if any(a['severity'] == 'HIGH' for a in alerts) else ('MEDIUM' if alerts else 'LOW'),
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='财务异常检测')
    parser.add_argument('--ts_code', required=True, help='股票代码')
    parser.add_argument('--report_date', default=None, help='报告日期')
    args = parser.parse_args()

    result = run_analysis(args.ts_code, args.report_date)
    print(format_output(result))
    print("\n---JSON---")
    parsed = parse_alerts(result)
    print(json.dumps(parsed, ensure_ascii=False, default=str))
