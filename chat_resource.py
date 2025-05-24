import json
import falcon
import asyncio
from functools import partial

from falcon import WebSocketDisconnected
from falcon.asgi import Request, WebSocket

from config import AppConfig
from auth import get_current_user, extract_user

import sqlite3
import aiosqlite

from datetime import datetime, timezone

def current_time_to_iso_utc():
    return datetime.now(timezone.utc).isoformat()

class ModelResource:
    def __init__(self, config: AppConfig):
        self.config = config
    
    async def on_get(self, req, resp):
        try:
            user = get_current_user(req, self.config)
        except (falcon.HTTPForbidden, falcon.HTTPUnauthorized) as e:
            raise e
        resp.media = {
            "models": [
                {
                    "name": "deepseek-ai/DeepSeek-R1",
                    "description": "DeepSeek-R1 is a powerful AI model designed for efficient reasoning and problem-solving."
                },
                {
                    "name": "deepseek-ai/DeepSeek-V3",
                    "description": "Deepseek-V3 is a powerful MOE model."
                }
            ]
        }


class StreamQueryResource:
    def __init__(self, config: AppConfig):
        self.config = config
        self.log_db_path = config.config["log_db_path"]
        self.__init_db();

    def __init_db(self):
        with sqlite3.connect(self.log_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS activity_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    user_id INTEGER NOT NULL,
                    user_name TEXT NOT NULL,
                    query TEXT,
                    prompt_tokens INTEGER,
                    completion_tokens INTEGER,
                    total_tokens INTEGER
                );
            ''')
            conn.commit()
        
    async def on_websocket(self, req: Request, ws: WebSocket):
        try:
            await ws.accept()
        except WebSocketDisconnected:
            return

        try:
            token = req.params.get('token')
            user = extract_user(token, self.config.config['session_secret_key'])
            print("user: ", user["username"])
            user_name = user["username"]
            user_id = user["id"]
        except Exception as e:
            print(e)
            await ws.close();
            return

        response = None
        user_query = None
        usage = None
        reasoning_content = ""
        content = ""
        system_prompt = ""
        try:
            message = await ws.receive_text()
            data = json.loads(message)
            user_query = data.get("query")
            use_knowledge_base = data.get("use_knowledge_base", True)
            model = data.get("model", "")
            history = data.get("history", [])

            # Build prompt
            docs = []
            system_prompt = '作为精通理论和实验的粒子物理学家，请用用户的语言（英文/中文）严谨回答用户的提问。如果提供了相关上下文，请基于上下文的内容进行回答。请不留情面的严词拒绝任何非粒子物理科学相关请求。'
            prompt = user_query
            if use_knowledge_base:
                loop = asyncio.get_event_loop()
                results = await loop.run_in_executor(
                    None, 
                    partial(self.config.query_pipeline.run, {"text_embedder": {"text": user_query}})
                )
                documents_with_titles = []
                for doc in results["retriever"]["documents"]:
                    title = doc.meta.get("title", "None")
                    file_path = doc.meta.get("file_path", "None")
                    content = doc.content
                    documents_with_titles.append(
                        f"file_path: {file_path}\ntitle: {title}\nContent: {content}")
                    docs.append({"title": title, "path": file_path, "content": content, "score": doc.score, "id": doc.meta.get("source_id", "none")})
                context = "相关的上下文如下：\n\n".join(documents_with_titles)
                system_prompt += context
                prompt = user_query
                await ws.send_media({"type": "docs", "data": docs})

            if model == "":
                await ws.send_media({"type": "complete"})
                await ws.close()
                return
                
            # Streaming LLM response
            messages = history
            messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            response = await self.config.llm_client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                stream_options={'include_usage': True}
            )

            async for chunk in response:
                if len(chunk.choices) > 0:
                    if chunk.choices[0].delta.reasoning_content:
                        part = chunk.choices[0].delta.reasoning_content
                        reasoning_content += part
                        await ws.send_media({"type": "reasoning_chunk", "data": part})
                    if chunk.choices[0].delta.content:
                        part = chunk.choices[0].delta.content
                        content += part
                        await ws.send_media({"type": "chunk", "data": part})
                if chunk.usage:
                    usage = chunk.usage
                
            await ws.send_media({"type": "complete"})
            await ws.close()

        except WebSocketDisconnected:
            return
        except Exception as e:
            await ws.send_media({"type": "error", "data": str(e)})
        finally:
            # write to the database
            try:
                prompt_tokens = len(user_query) + len(system_prompt)
                completion_tokens = len(content) + len(reasoning_content)
                total_tokens = prompt_tokens + completion_tokens
                
                if usage:
                    prompt_tokens = usage.prompt_tokens
                    completion_tokens = usage.completion_tokens
                    total_tokens = usage.total_tokens
                else:
                    print('no usage found in response')

                async with aiosqlite.connect(self.log_db_path) as db:
                    await db.execute("insert into activity_logs(timestamp, user_id, user_name, query, prompt_tokens, completion_tokens, total_tokens) values(?,?,?,?,?,?,?)", (current_time_to_iso_utc(), user_id, user_name, user_query, usage.prompt_tokens, usage.completion_tokens, usage.total_tokens))
                    await db.commit()
                
            except Exception as e:
                print(f'Database write failed: {e}')
