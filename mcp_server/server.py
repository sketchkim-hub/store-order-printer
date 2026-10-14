# -*- coding: utf-8 -*-
"""매장용 주문 프린터 - 읽기 전용 MCP 서버 (stdio).
도구: get_today_sales, get_item_sales, get_menu. 인쇄/수정/쓰기 기능 없음."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp.server.fastmcp import FastMCP
import sales_reader as sr

mcp = FastMCP("store-order-printer")

def _base():
    return sr.resolve_data_dir()

def _safe(fn, *a):
    try:
        return fn(*a)
    except sr.DataError as e:
        return {"error": str(e)}

@mcp.tool()
def get_today_sales() -> dict:
    """오늘(이 컴퓨터 날짜) 매출: 총액(total, 원), 주문(영수증) 수, 판매 수량, 품목별 수량·금액."""
    return _safe(sr.today_sales, _base())

@mcp.tool()
def get_item_sales(start_date: str, end_date: str) -> dict:
    """기간 매출 (날짜 포함, YYYY-MM-DD, 최대 366일): 품목별 수량·금액 합계와 일별 총액."""
    return _safe(sr.item_sales, _base(), start_date, end_date)

@mcp.tool()
def get_menu() -> dict:
    """현재 메뉴 목록: 단축키 번호(key), 품목(name), 가격(price, 원)."""
    return _safe(sr.menu, _base())

if __name__ == "__main__":
    mcp.run()  # stdio
