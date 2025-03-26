import logging
import json
import os
from datetime import datetime

from alipay.aop.api.AlipayClientConfig import AlipayClientConfig
from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
from alipay.aop.api.domain.AlipayTradePrecreateModel import AlipayTradePrecreateModel
from alipay.aop.api.domain.AlipayTradeQueryModel import AlipayTradeQueryModel
from alipay.aop.api.request.AlipayTradePrecreateRequest import AlipayTradePrecreateRequest
from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest

# 正式环境
from utils.config import (
    ALIPAY_APPID,
    APP_PRIVATE_KEY,
    ALIPAY_PUBLIC_KEY,
)

# 沙箱环境
from utils.config import (
    SAND_BOX_APPID,
    SAND_BOX_APP_PRIVATE_KEY,
    SAND_BOX_ALIPAY_PUBLIC_KEY,
)


class AlipayClient:
    """
    支付宝支付客户端类。
    
    提供支付宝当面付相关接口的封装，包括交易预创建（生成二维码）和交易查询功能。
    支持沙箱环境和正式环境的配置切换。

    Attributes:
        logger: 日志记录器实例
        alipay_client_config: 支付宝客户端配置实例
        client: 支付宝DefaultAlipayClient实例
    """

    def __init__(self, sandbox=True):
        """
        初始化支付宝客户端。

        Args:
            sandbox (bool): 是否使用沙箱环境，默认为True
        """
        # 创建logs目录（如果不存在）
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # 配置日志
        log_file = os.path.join(log_dir, f'alipay_{datetime.now().strftime("%Y%m%d")}.log')
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('')
        self.logger.info(f"初始化支付宝客户端 - {'沙箱环境' if sandbox else '正式环境'}")

        # 初始化支付宝客户端配置
        self.alipay_client_config = AlipayClientConfig()

        # 根据环境设置不同的服务器地址
        # 由于sdk里的沙箱地址并没有更新，所以这里手动设置
        if sandbox:
            self.alipay_client_config.app_id = SAND_BOX_APPID
            self.alipay_client_config.app_private_key = SAND_BOX_APP_PRIVATE_KEY
            self.alipay_client_config.alipay_public_key = SAND_BOX_ALIPAY_PUBLIC_KEY
            self.alipay_client_config.server_url = 'https://openapi-sandbox.dl.alipaydev.com/gateway.do'

        else:
            self.alipay_client_config.app_id = ALIPAY_APPID
            self.alipay_client_config.app_private_key = APP_PRIVATE_KEY
            self.alipay_client_config.alipay_public_key = ALIPAY_PUBLIC_KEY
            self.alipay_client_config.server_url = 'https://openapi.alipay.com/gateway.do'
        
        self.alipay_client_config.timeout = 30
        
        # 初始化客户端
        self.client = DefaultAlipayClient(self.alipay_client_config, self.logger)

    def trade_precreate(self, out_trade_no, total_amount, subject,
                        timeout_express='30m', **kwargs):
        """
        预创建交易接口，生成支付二维码。

        Args:
            out_trade_no (str): 商户订单号，由商户自定义，需保证在商户端不重复
            total_amount (float): 订单总金额，单位为元，精确到小数点后两位
            subject (str): 订单标题
            timeout_express (str, optional): 订单有效期，格式为"15m", 表示15分钟, 二维码最长有效期是2小时, 不管该参数传递的值是多少, 超过2小时后二维码都将失效不能再进行扫码支付，
                当订单超时后，依然能够查询订单的状态，但此时用户将无法支付，所以超时后直接返回订单关闭即可。但有时似乎也不生效，具体原因不明。
            **kwargs: 其他可选参数, 参考支付宝API文档 https://opendocs.alipay.com/open/02np92

        Returns:
            dict: 包含以下字段的字典：
                - success (bool): 是否成功
                - qr_code (str): 当success为True时，返回二维码链接
                - error_msg (str): 当success为False时，返回错误信息
        """
        self.logger.info(f"创建订单 - 订单号:{out_trade_no}, 金额:{total_amount}, 商品:{subject}")
        try:
            model = AlipayTradePrecreateModel()
            model.out_trade_no = out_trade_no
            model.total_amount = str(total_amount)
            model.subject = subject
            model.timeout_express = timeout_express

            for k, v in kwargs.items():
                setattr(model, k, v)
                
            request = AlipayTradePrecreateRequest(biz_model=model)
            response = self.client.execute(request)
            self.logger.debug(f"支付宝响应原始数据: {response}")
            
            if isinstance(response, bytes):
                response = response.decode('utf-8')
            response = json.loads(response)
            self.logger.info(f"订单创建结果: {response}")

            if response.get('code') == '10000':
                self.logger.info(f"订单创建成功 - 订单号:{out_trade_no}")
                return {'success': True, 'qr_code': response['qr_code']}
            else:
                self.logger.error(f"订单创建失败 - 订单号:{out_trade_no}, 错误:{response.get('msg')}")
                return {'success': False, 'error_msg': response.get('msg') or '创建二维码失败'}
                
        except Exception as e:
            self.logger.error(f"创建订单异常 - 订单号:{out_trade_no}, 异常:{str(e)}", exc_info=True)
            return {'success': False, 'error_msg': str(e)}

    def trade_query(self, out_trade_no=None, trade_no=None):
        """
        交易查询接口，查询订单支付状态。

        Args:
            out_trade_no (str, optional): 商户订单号, 这个demo中应使用此参数
            trade_no (str, optional): 支付宝交易号

        Notes:
            out_trade_no和trade_no至少要传入一个

        Returns:
            dict: 包含以下字段的字典：
                - success (bool): 是否成功
                - msg (str): 结果信息
                - data (dict): 支付宝返回的原始数据
        """
        self.logger.info(f"查询订单 - 商户订单号:{out_trade_no}, 支付宝交易号:{trade_no}")
        try:
            model = AlipayTradeQueryModel()
            if out_trade_no:
                model.out_trade_no = out_trade_no
            if trade_no:
                model.trade_no = trade_no

            request = AlipayTradeQueryRequest(biz_model=model)
            response = self.client.execute(request)
            self.logger.debug(f"查询响应原始数据: {response}")

            if isinstance(response, bytes):
                response = response.decode('utf-8')
            response_json = json.loads(response)
            self.logger.info(f"查询结果: {response_json}")
            
            # 处理交易不存在的情况
            if response_json.get('code') == '40004' and response_json.get('sub_code') == 'ACQ.TRADE_NOT_EXIST':
                self.logger.info(f"订单不存在或未支付 - 商户订单号:{out_trade_no}")
                return {
                    'success': False,
                    'msg': '支付未成功',
                    'data': response_json
                }
            
            # 处理成功查询的情况
            if response_json.get('code') == '10000':
                self.logger.info(f"查询成功 - 订单状态:{response_json.get('trade_status')}")
                return {
                    'success': True,
                    'msg': '查询成功',
                    'data': response_json
                }
                
            # 处理其他异常情况
            self.logger.error(f"查询失败 - 错误信息:{response_json.get('msg')}")
            return {
                'success': False,
                'msg': response_json.get('msg') or '查询失败',
                'data': response_json
            }
            
        except Exception as e:
            self.logger.error(f"查询订单异常: {str(e)}", exc_info=True)
            return {
                'success': False,
                'msg': str(e),
                'data': None
            }
