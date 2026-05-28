"""
智能记忆管理器 — 语义化存储与检索
零依赖实现 TF-IDF + 余弦相似度，替代全文加载

使用方法：
  from smart_memory import SmartMemory
  
  mem = SmartMemory()
  mem.remember("3DGS truck PSNR=25.8, densification=0.005")
  results = mem.recall("3DGS 实验参数")
"""

import json
import math
import os
import pathlib
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ── 配置 ──────────────────────────────────────────────────

SHARED_DIR = pathlib.Path.home() / ".shared-memory"
MEMORY_DB = SHARED_DIR / ".memory_vectors.json"
KNOWLEDGE_DB = SHARED_DIR / ".knowledge_base.json"

# ── 中文分词（简单实现，无依赖）──────────────────────────

# 常用停用词
STOP_WORDS = set([
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
    "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "it", "its", "this", "that", "these", "those", "i", "you",
    "he", "she", "we", "they", "me", "him", "her", "us", "them",
])

def tokenize(text: str) -> List[str]:
    """简单分词：英文按空格+标点，中文按字符（无外部依赖）"""
    # 英文分词
    text = re.sub(r'[^\w\u4e00-\u9fff]', ' ', text.lower())
    tokens = []
    
    # 分离中文和英文
    current_en = []
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            # 中文字符
            if current_en:
                tokens.extend(''.join(current_en).split())
                current_en = []
            tokens.append(char)
        elif char.isalnum() or char == ' ':
            current_en.append(char)
        else:
            if current_en:
                tokens.extend(''.join(current_en).split())
                current_en = []
    
    if current_en:
        tokens.extend(''.join(current_en).split())
    
    # 中文二元组（bigram）
    cn_chars = [t for t in tokens if '\u4e00' <= t <= '\u9fff']
    for i in range(len(cn_chars) - 1):
        tokens.append(cn_chars[i] + cn_chars[i+1])
    
    # 过滤停用词和短词
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]

# ── TF-IDF 向量化 ─────────────────────────────────────────

class TFIDFVectorizer:
    """零依赖 TF-IDF 向量化器"""
    
    def __init__(self):
        self.vocabulary: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}
        self.documents: List[List[str]] = []
    
    def fit(self, documents: List[str]):
        """训练词汇表和 IDF"""
        self.documents = [tokenize(doc) for doc in documents]
        
        # 构建词汇表
        all_tokens = set()
        for doc_tokens in self.documents:
            all_tokens.update(doc_tokens)
        
        self.vocabulary = {token: idx for idx, token in enumerate(sorted(all_tokens))}
        
        # 计算 IDF
        n_docs = len(self.documents)
        doc_freq = Counter()
        for doc_tokens in self.documents:
            unique_tokens = set(doc_tokens)
            for token in unique_tokens:
                doc_freq[token] += 1
        
        self.idf = {}
        for token in self.vocabulary:
            df = doc_freq.get(token, 0)
            self.idf[token] = math.log((n_docs + 1) / (df + 1)) + 1
    
    def transform(self, text: str) -> Dict[int, float]:
        """将文本转换为稀疏向量"""
        tokens = tokenize(text)
        if not tokens:
            return {}
        
        # 计算 TF
        tf = Counter(tokens)
        max_tf = max(tf.values()) if tf else 1
        
        # 计算 TF-IDF
        vector = {}
        for token, count in tf.items():
            if token in self.vocabulary:
                idx = self.vocabulary[token]
                tf_score = 0.5 + 0.5 * (count / max_tf)  # 归一化 TF
                idf_score = self.idf.get(token, 1.0)
                vector[idx] = tf_score * idf_score
        
        return vector
    
    def cosine_similarity(self, vec1: Dict[int, float], vec2: Dict[int, float]) -> float:
        """计算余弦相似度"""
        if not vec1 or not vec2:
            return 0.0
        
        # 公共维度
        common_keys = set(vec1.keys()) & set(vec2.keys())
        if not common_keys:
            return 0.0
        
        dot_product = sum(vec1[k] * vec2[k] for k in common_keys)
        norm1 = math.sqrt(sum(v * v for v in vec1.values()))
        norm2 = math.sqrt(sum(v * v for v in vec2.values()))
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)

# ── 智能记忆管理器 ────────────────────────────────────────

class SmartMemory:
    """语义化记忆管理器"""
    
    def __init__(self, memory_dir: Optional[pathlib.Path] = None):
        self.memory_dir = memory_dir or SHARED_DIR
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.memory_db_path = self.memory_dir / ".memory_vectors.json"
        self.knowledge_db_path = self.memory_dir / ".knowledge_base.json"
        
        # 加载或初始化
        self.memories = self._load_json(self.memory_db_path, [])
        self.knowledge = self._load_json(self.knowledge_db_path, {
            "bugs": [],      # Bug 解决方案
            "decisions": [], # 技术决策
            "experiments": [],# 实验记录
            "patterns": [],  # 代码模式
        })
        
        # 初始化向量化器
        self.vectorizer = TFIDFVectorizer()
        self._rebuild_index()
    
    def _load_json(self, path: pathlib.Path, default):
        """加载 JSON 文件"""
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except:
                return default
        return default
    
    def _save_json(self, path: pathlib.Path, data):
        """保存 JSON 文件"""
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    def _rebuild_index(self):
        """重建向量索引"""
        texts = [m["text"] for m in self.memories]
        if texts:
            self.vectorizer.fit(texts)
        else:
            self.vectorizer.fit(["初始化"])
    
    # ── 核心 API ──────────────────────────────────────────
    
    def remember(self, text: str, category: str = "general", 
                 tags: List[str] = None, source: str = "user") -> dict:
        """存储记忆"""
        memory = {
            "id": len(self.memories) + 1,
            "text": text,
            "category": category,
            "tags": tags or [],
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "access_count": 0,
        }
        
        self.memories.append(memory)
        self._save_json(self.memory_db_path, self.memories)
        self._rebuild_index()
        
        return memory
    
    def recall(self, query: str, top_k: int = 5, 
               category: Optional[str] = None) -> List[dict]:
        """语义检索记忆"""
        if not self.memories:
            return []
        
        query_vec = self.vectorizer.transform(query)
        
        # 计算相似度
        results = []
        for i, memory in enumerate(self.memories):
            if category and memory.get("category") != category:
                continue
            
            if i < len(self.vectorizer.documents):
                doc_text = memory["text"]
                doc_vec = self.vectorizer.transform(doc_text)
                similarity = self.vectorizer.cosine_similarity(query_vec, doc_vec)
                
                if similarity > 0.01:  # 阈值过滤
                    results.append({
                        **memory,
                        "similarity": round(similarity, 4),
                    })
        
        # 按相似度排序
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        # 更新访问计数
        for result in results[:top_k]:
            for m in self.memories:
                if m["id"] == result["id"]:
                    m["access_count"] = m.get("access_count", 0) + 1
        
        self._save_json(self.memory_db_path, self.memories)
        
        return results[:top_k]
    
    # ── 知识库 API ────────────────────────────────────────
    
    def add_bug_solution(self, problem: str, solution: str, 
                         context: str = "", tags: List[str] = None):
        """记录 Bug 解决方案"""
        entry = {
            "id": len(self.knowledge["bugs"]) + 1,
            "problem": problem,
            "solution": solution,
            "context": context,
            "tags": tags or [],
            "timestamp": datetime.now().isoformat(),
            "usage_count": 0,
        }
        
        self.knowledge["bugs"].append(entry)
        self._save_json(self.knowledge_db_path, self.knowledge)
        
        # 同时存入记忆
        self.remember(
            f"Bug解决方案: {problem} -> {solution}",
            category="bug_fix",
            tags=tags or ["bug", "solution"],
        )
        
        return entry
    
    def find_bug_solution(self, problem: str, top_k: int = 3) -> List[dict]:
        """查找相似 Bug 解决方案"""
        if not self.knowledge["bugs"]:
            return []
        
        # 向量化所有 bug 描述
        bug_texts = [b["problem"] + " " + b.get("context", "") 
                     for b in self.knowledge["bugs"]]
        
        temp_vectorizer = TFIDFVectorizer()
        temp_vectorizer.fit(bug_texts + [problem])
        
        query_vec = temp_vectorizer.transform(problem)
        
        results = []
        for i, bug in enumerate(self.knowledge["bugs"]):
            doc_vec = temp_vectorizer.transform(bug_texts[i])
            similarity = temp_vectorizer.cosine_similarity(query_vec, doc_vec)
            
            if similarity > 0.01:
                results.append({
                    **bug,
                    "similarity": round(similarity, 4),
                })
        
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
        # 更新使用计数
        for result in results[:top_k]:
            for b in self.knowledge["bugs"]:
                if b["id"] == result["id"]:
                    b["usage_count"] = b.get("usage_count", 0) + 1
        
        self._save_json(self.knowledge_db_path, self.knowledge)
        
        return results[:top_k]
    
    def add_decision(self, decision: str, reason: str, 
                     alternatives: List[str] = None):
        """记录技术决策"""
        entry = {
            "id": len(self.knowledge["decisions"]) + 1,
            "decision": decision,
            "reason": reason,
            "alternatives": alternatives or [],
            "timestamp": datetime.now().isoformat(),
        }
        
        self.knowledge["decisions"].append(entry)
        self._save_json(self.knowledge_db_path, self.knowledge)
        
        self.remember(
            f"技术决策: {decision}，原因: {reason}",
            category="decision",
            tags=["decision", "architecture"],
        )
        
        return entry
    
    def add_experiment(self, name: str, params: dict, 
                       results: dict, conclusion: str = ""):
        """记录实验结果"""
        entry = {
            "id": len(self.knowledge["experiments"]) + 1,
            "name": name,
            "params": params,
            "results": results,
            "conclusion": conclusion,
            "timestamp": datetime.now().isoformat(),
        }
        
        self.knowledge["experiments"].append(entry)
        self._save_json(self.knowledge_db_path, self.knowledge)
        
        # 构建可搜索的文本
        params_str = ", ".join(f"{k}={v}" for k, v in params.items())
        results_str = ", ".join(f"{k}={v}" for k, v in results.items())
        
        self.remember(
            f"实验 {name}: 参数[{params_str}] -> 结果[{results_str}] {conclusion}",
            category="experiment",
            tags=["experiment", name],
        )
        
        return entry
    
    def find_experiment(self, query: str, top_k: int = 3) -> List[dict]:
        """查找相似实验"""
        if not self.knowledge["experiments"]:
            return []
        
        exp_texts = [
            f"{e['name']} {json.dumps(e['params'])} {json.dumps(e['results'])} {e.get('conclusion', '')}"
            for e in self.knowledge["experiments"]
        ]
        
        temp_vectorizer = TFIDFVectorizer()
        temp_vectorizer.fit(exp_texts + [query])
        
        query_vec = temp_vectorizer.transform(query)
        
        results = []
        for i, exp in enumerate(self.knowledge["experiments"]):
            doc_vec = temp_vectorizer.transform(exp_texts[i])
            similarity = temp_vectorizer.cosine_similarity(query_vec, doc_vec)
            
            if similarity > 0.01:
                results.append({
                    **exp,
                    "similarity": round(similarity, 4),
                })
        
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]
    
    # ── 统计 API ──────────────────────────────────────────
    
    def stats(self) -> dict:
        """获取记忆统计"""
        return {
            "total_memories": len(self.memories),
            "total_bugs": len(self.knowledge["bugs"]),
            "total_decisions": len(self.knowledge["decisions"]),
            "total_experiments": len(self.knowledge["experiments"]),
            "categories": Counter(m.get("category") for m in self.memories),
            "memory_size_kb": self.memory_db_path.stat().st_size / 1024 if self.memory_db_path.exists() else 0,
        }
    
    def export_markdown(self) -> str:
        """导出为 Markdown 格式"""
        lines = ["# 智能记忆库导出\n"]
        lines.append(f"导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 统计
        stats = self.stats()
        lines.append(f"## 统计\n")
        lines.append(f"- 记忆条目: {stats['total_memories']}")
        lines.append(f"- Bug 解决方案: {stats['total_bugs']}")
        lines.append(f"- 技术决策: {stats['total_decisions']}")
        lines.append(f"- 实验记录: {stats['total_experiments']}\n")
        
        # Bug 解决方案
        if self.knowledge["bugs"]:
            lines.append("## Bug 解决方案\n")
            for bug in self.knowledge["bugs"]:
                lines.append(f"### #{bug['id']} {bug['problem'][:50]}...")
                lines.append(f"**问题**: {bug['problem']}")
                lines.append(f"**解决方案**: {bug['solution']}")
                if bug.get('context'):
                    lines.append(f"**上下文**: {bug['context']}")
                lines.append(f"**使用次数**: {bug.get('usage_count', 0)}\n")
        
        # 实验记录
        if self.knowledge["experiments"]:
            lines.append("## 实验记录\n")
            for exp in self.knowledge["experiments"]:
                lines.append(f"### #{exp['id']} {exp['name']}")
                lines.append(f"**参数**: {json.dumps(exp['params'], ensure_ascii=False)}")
                lines.append(f"**结果**: {json.dumps(exp['results'], ensure_ascii=False)}")
                if exp.get('conclusion'):
                    lines.append(f"**结论**: {exp['conclusion']}")
                lines.append("")
        
        return "\n".join(lines)

# ── CLI 接口 ──────────────────────────────────────────────

def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="智能记忆管理器")
    subparsers = parser.add_subparsers(dest="command")
    
    # remember 命令
    remember_parser = subparsers.add_parser("remember", help="存储记忆")
    remember_parser.add_argument("text", help="记忆内容")
    remember_parser.add_argument("--category", "-c", default="general", help="分类")
    remember_parser.add_argument("--tags", "-t", nargs="*", help="标签")
    
    # recall 命令
    recall_parser = subparsers.add_parser("recall", help="检索记忆")
    recall_parser.add_argument("query", help="查询内容")
    recall_parser.add_argument("--top-k", "-k", type=int, default=5, help="返回数量")
    recall_parser.add_argument("--category", "-c", help="过滤分类")
    
    # bug 命令
    bug_parser = subparsers.add_parser("bug", help="Bug 解决方案")
    bug_subparsers = bug_parser.add_subparsers(dest="bug_action")
    
    bug_add = bug_subparsers.add_parser("add", help="添加解决方案")
    bug_add.add_argument("problem", help="问题描述")
    bug_add.add_argument("solution", help="解决方案")
    bug_add.add_argument("--context", default="", help="上下文")
    bug_add.add_argument("--tags", nargs="*", help="标签")
    
    bug_find = bug_subparsers.add_parser("find", help="查找解决方案")
    bug_find.add_argument("query", help="查询问题")
    bug_find.add_argument("--top-k", "-k", type=int, default=3, help="返回数量")
    
    # experiment 命令
    exp_parser = subparsers.add_parser("experiment", help="实验记录")
    exp_subparsers = exp_parser.add_subparsers(dest="exp_action")
    
    exp_add = exp_subparsers.add_parser("add", help="添加实验")
    exp_add.add_argument("name", help="实验名称")
    exp_add.add_argument("--params", "-p", required=True, help="参数 (JSON)")
    exp_add.add_argument("--results", "-r", required=True, help="结果 (JSON)")
    exp_add.add_argument("--conclusion", "-c", default="", help="结论")
    
    exp_find = exp_subparsers.add_parser("find", help="查找实验")
    exp_find.add_argument("query", help="查询内容")
    exp_find.add_argument("--top-k", "-k", type=int, default=3, help="返回数量")
    
    # stats 命令
    subparsers.add_parser("stats", help="查看统计")
    
    # export 命令
    subparsers.add_parser("export", help="导出 Markdown")
    
    args = parser.parse_args()
    
    mem = SmartMemory()
    
    if args.command == "remember":
        result = mem.remember(args.text, args.category, args.tags)
        print(f"✅ 记忆已存储 (ID: {result['id']})")
    
    elif args.command == "recall":
        results = mem.recall(args.query, args.top_k, args.category)
        if results:
            print(f"🔍 找到 {len(results)} 条相关记忆:\n")
            for i, r in enumerate(results, 1):
                print(f"{i}. [相似度: {r['similarity']}] {r['text']}")
                print(f"   分类: {r['category']} | 访问: {r['access_count']}次")
                print()
        else:
            print("❌ 未找到相关记忆")
    
    elif args.command == "bug":
        if args.bug_action == "add":
            result = mem.add_bug_solution(args.problem, args.solution, 
                                          args.context, args.tags)
            print(f"✅ Bug 解决方案已记录 (ID: {result['id']})")
        elif args.bug_action == "find":
            results = mem.find_bug_solution(args.query, args.top_k)
            if results:
                print(f"🔍 找到 {len(results)} 个相似问题:\n")
                for i, r in enumerate(results, 1):
                    print(f"{i}. [相似度: {r['similarity']}] {r['problem']}")
                    print(f"   解决方案: {r['solution']}")
                    print(f"   使用次数: {r.get('usage_count', 0)}")
                    print()
            else:
                print("❌ 未找到相似问题")
    
    elif args.command == "experiment":
        if args.exp_action == "add":
            params = json.loads(args.params)
            results = json.loads(args.results)
            result = mem.add_experiment(args.name, params, results, args.conclusion)
            print(f"✅ 实验记录已保存 (ID: {result['id']})")
        elif args.exp_action == "find":
            results = mem.find_experiment(args.query, args.top_k)
            if results:
                print(f"🔍 找到 {len(results)} 个相关实验:\n")
                for i, r in enumerate(results, 1):
                    print(f"{i}. [相似度: {r['similarity']}] {r['name']}")
                    print(f"   参数: {json.dumps(r['params'], ensure_ascii=False)}")
                    print(f"   结果: {json.dumps(r['results'], ensure_ascii=False)}")
                    print()
            else:
                print("❌ 未找到相关实验")
    
    elif args.command == "stats":
        stats = mem.stats()
        print("📊 记忆库统计:\n")
        print(f"  记忆条目: {stats['total_memories']}")
        print(f"  Bug 解决方案: {stats['total_bugs']}")
        print(f"  技术决策: {stats['total_decisions']}")
        print(f"  实验记录: {stats['total_experiments']}")
        print(f"  存储大小: {stats['memory_size_kb']:.2f} KB")
        print(f"\n  分类分布:")
        for cat, count in stats['categories'].items():
            print(f"    {cat}: {count}")
    
    elif args.command == "export":
        markdown = mem.export_markdown()
        print(markdown)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
