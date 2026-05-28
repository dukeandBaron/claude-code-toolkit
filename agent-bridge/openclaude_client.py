"""
OpenClaude gRPC 客户端原型

用于测试与 OpenClaude 的 gRPC 集成。

使用前需要：
1. 安装 OpenClaude: npm install -g @gitlawb/openclaude
2. 启动 gRPC 服务器: openclaude --grpc
3. 生成 Python gRPC 客户端: python generate_grpc.py

注意：这是一个原型，实际使用需要先生成 gRPC 客户端代码。
"""

import json
import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))


class OpenClaudeClient:
    """OpenClaude gRPC 客户端封装"""
    
    def __init__(self, host="localhost", port=50051):
        self.host = host
        self.port = port
        self.channel = None
        self.stub = None
        
    def connect(self):
        """连接到 OpenClaude gRPC 服务器"""
        try:
            import grpc
            # 注意：需要先生成 gRPC 客户端代码
            # from openclaude_pb2 import *
            # from openclaude_pb2_grpc import AgentServiceStub
            
            self.channel = grpc.insecure_channel(f'{self.host}:{self.port}')
            # self.stub = AgentServiceStub(self.channel)
            print(f"✅ 已连接到 OpenClaude gRPC 服务器 ({self.host}:{self.port})")
            return True
        except ImportError:
            print("❌ 未安装 grpcio，请运行: pip install grpcio grpcio-tools")
            return False
        except Exception as e:
            print(f"❌ 连接失败: {e}")
            return False
    
    def chat(self, message, working_dir="."):
        """发送消息到 OpenClaude"""
        if not self.stub:
            print("❌ 未连接到服务器")
            return None
        
        # 这里需要实际的 gRPC 调用
        # 暂时返回模拟响应
        print(f"📤 发送消息: {message}")
        print(f"📁 工作目录: {working_dir}")
        
        # 模拟响应
        return {
            "text": f"OpenClaude 收到: {message}",
            "tool_calls": [],
            "tokens": {"prompt": 0, "completion": 0}
        }
    
    def execute_task(self, task_description, working_dir="."):
        """执行编码任务"""
        print(f"🚀 执行任务: {task_description}")
        
        # 这里应该调用 OpenClaude 的 gRPC API
        # 暂时返回模拟结果
        return {
            "success": True,
            "result": f"任务完成: {task_description}",
            "files_modified": [],
            "tokens_used": 0
        }


def generate_grpc_client():
    """生成 Python gRPC 客户端代码"""
    print("📝 生成 Python gRPC 客户端...")
    print()
    print("步骤：")
    print("1. 确保已安装 grpcio-tools:")
    print("   pip install grpcio grpcio-tools")
    print()
    print("2. 下载 proto 文件:")
    print("   curl -O https://raw.githubusercontent.com/Gitlawb/openclaude/main/src/proto/openclaude.proto")
    print()
    print("3. 生成 Python 代码:")
    print("   python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. openclaude.proto")
    print()
    print("4. 生成的文件:")
    print("   - openclaude_pb2.py")
    print("   - openclaude_pb2_grpc.py")


def test_connection():
    """测试连接"""
    print("🧪 测试 OpenClaude 连接...")
    print()
    
    client = OpenClaudeClient()
    
    # 测试连接
    if client.connect():
        # 测试发送消息
        response = client.chat("Hello from Claude Code Toolkit!")
        print(f"📨 响应: {response}")
    
    print()
    print("💡 提示: 这是原型代码，实际使用需要:")
    print("   1. 启动 OpenClaude gRPC 服务器")
    print("   2. 生成 Python gRPC 客户端")
    print("   3. 实现实际的 gRPC 调用")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="OpenClaude gRPC 客户端")
    subparsers = parser.add_subparsers(dest="command")
    
    # 生成 gRPC 客户端
    subparsers.add_parser("generate", help="生成 gRPC 客户端代码")
    
    # 测试连接
    subparsers.add_parser("test", help="测试连接")
    
    # 聊天
    chat_parser = subparsers.add_parser("chat", help="发送消息")
    chat_parser.add_argument("message", help="消息内容")
    chat_parser.add_argument("--dir", default=".", help="工作目录")
    
    args = parser.parse_args()
    
    if args.command == "generate":
        generate_grpc_client()
    elif args.command == "test":
        test_connection()
    elif args.command == "chat":
        client = OpenClaudeClient()
        if client.connect():
            client.chat(args.message, args.dir)
    else:
        parser.print_help()
