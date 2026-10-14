# stdio 로 실제 서버를 띄워 mcp 클라이언트로 각 도구 호출
import os, sys, json, asyncio, datetime
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import sampledata
from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
TODAY = datetime.date.today().isoformat()
d = sampledata.make(TODAY); before = sampledata.snapshot(d)
def data(res):
    assert not res.isError, res
    if getattr(res, "structuredContent", None):
        sc = res.structuredContent; return sc.get("result", sc)
    return json.loads(res.content[0].text)
async def main():
    env = dict(os.environ, FESTIVAL_RECEIPT_DATA_DIR=d)
    p = StdioServerParameters(command=sys.executable, args=[os.path.join(os.path.dirname(HERE), "server.py")], env=env)
    async with stdio_client(p) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            names = sorted(t.name for t in (await s.list_tools()).tools)
            assert names == ["get_item_sales", "get_menu", "get_today_sales"], names
            t = data(await s.call_tool("get_today_sales", {}))
            assert t["total"] == 26000 and t["order_count"] == 3, t
            r2 = data(await s.call_tool("get_item_sales", {"start_date": "2026-10-01", "end_date": TODAY}))
            assert r2["total"] >= 26000 and r2["daily"], r2
            bad = data(await s.call_tool("get_item_sales", {"start_date": "2026-99-01", "end_date": TODAY}))
            assert "error" in bad, bad
            m = data(await s.call_tool("get_menu", {}))
            assert [x["name"] for x in m["items"]] == ["떡볶이", "어묵", "꽈배기,도너츠"], m
            print("tools:", names); print("today:", t["total"], t["order_count"], t["item_count"]); print("bad date ->", bad["error"])
asyncio.run(main())
assert sampledata.snapshot(d) == before, "data dir changed!"
print("E2E TESTS OK")
