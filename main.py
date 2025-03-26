import time
import qrcode
import io
import base64
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from utils.alipay_utils import AlipayClient

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 初始化支付宝客户端并设置默认使用沙箱环境
alipay_client = AlipayClient(sandbox=True)

@app.post("/api/toggle_sandbox")
async def toggle_sandbox(request: Request):
    """切换沙箱/正式环境"""
    try:
        data = await request.json()
        is_sandbox = data.get("sandbox", True)
        global alipay_client
        alipay_client = AlipayClient(sandbox=is_sandbox)
        return {"code": 0, "msg": "环境切换成功", "sandbox": is_sandbox}
    except Exception as e:
        return {"code": 1, "msg": str(e)}

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/query")
async def query(out_trade_no: str = None, trade_no: str = None):
    try:
        result = alipay_client.trade_query(
            out_trade_no=out_trade_no,
            trade_no=trade_no
        )
        if isinstance(result, dict):
            return JSONResponse(result.get('data', {}))
        return JSONResponse({
            "code": "40004", 
            "msg": "等待支付", 
            "trade_status": "WAIT_BUYER_PAY"
        })
    except Exception as e:
        # 出错时返回等待支付状态
        return JSONResponse({
            "code": "40004",
            "msg": "等待支付",
            "trade_status": "WAIT_BUYER_PAY"
        })

@app.get("/create_order")
async def create_order(amount: float, subject: str, timeout_express: str = '15m'):
    """创建订单并返回支付二维码"""
    try:
        # 验证timeout_express格式
        if not any(timeout_express.endswith(unit) for unit in ['m', 'h', 'd', 'c']):
            return {"code": 1, "detail": "超时时间格式错误，必须以m、h、d或c结尾"}
        
        # 提取数字部分
        if timeout_express == '1c':
            pass  # 1c是有效的特殊格式
        else:
            try:
                value = int(timeout_express[:-1])
                if value <= 0:
                    return {"code": 1, "detail": "超时时间必须大于0"}
            except ValueError:
                return {"code": 1, "detail": "超时时间必须是整数"}

        # 生成订单号 (年月日时分秒+4位随机数)
        order_id = time.strftime("%Y%m%d%H%M%S") + str(int(time.time() * 1000))[-4:]
        
        # 调用支付宝预创建订单接口
        result = alipay_client.trade_precreate(
            out_trade_no=order_id,
            total_amount=amount,
            subject=subject,
            timeout_express=timeout_express  # 使用用户传入的超时时间
        )
        
        if result.get('success'):
            # 生成二维码图片
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(result['qr_code'])
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 将图片转换为base64
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_str = base64.b64encode(img_buffer.getvalue()).decode()
            
            return {
                "code": 0,
                "qr_code": f"data:image/png;base64,{img_str}",  # 返回base64格式的二维码图片
                "order_id": order_id,
                "amount": amount
            }
        else:
            return {
                "code": 1,
                "detail": result.get('error_msg', '创建订单失败')
            }
            
    except Exception as e:
        return {"code": 1, "detail": str(e)}

@app.get("/check_order_status/{order_id}")
async def check_order_status(order_id: str):
    try:
        result = alipay_client.trade_query(out_trade_no=order_id)
        if result.get('success'):
            data = result.get('data', {})
            trade_status = data.get('trade_status')
            
            # 交易状态描述
            status_desc = {
                'WAIT_BUYER_PAY': '等待付款',
                'TRADE_CLOSED': '交易关闭',
                'TRADE_SUCCESS': '支付成功',
                'TRADE_FINISHED': '交易完成'
            }.get(trade_status, '未知状态')

            return {
                "code": 0,
                "status": trade_status,
                "status_desc": status_desc,
                "order_id": data.get('out_trade_no'),
                "trade_no": data.get('trade_no'),
                "amount": data.get('total_amount'),
                "buyer_info": {
                    "logon_id": data.get('buyer_logon_id'),
                    "user_id": data.get('buyer_user_id'),
                    "user_type": data.get('buyer_user_type')
                } if data.get('buyer_logon_id') else None
            }
        return {"code": 1, "msg": result.get('msg', '查询失败')}
    except Exception as e:
        return {"code": 1, "msg": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
