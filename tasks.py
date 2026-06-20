import os
from loguru import logger
from taskiq_redis import RedisAsyncResultBackend, ListQueueBroker
from browser_use import Agent

# Initialize Redis broker for Taskiq
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = os.getenv("REDIS_PORT", "6379")
redis_url = f"redis://{redis_host}:{redis_port}/0"

result_backend = RedisAsyncResultBackend(redis_url=redis_url)
broker = ListQueueBroker(url=redis_url).with_result_backend(result_backend)

@broker.task(task_name="run_browser_agent")
async def run_browser_agent_task(task_instructions: str, target_url: str) -> str:
    """
    Background worker task to execute the browser agent.
    This isolates the Playwright browser context into an independent asynchronous worker.
    """
    logger.info(f"🚀 [TASKIQ WORKER] Starting job for URL: {target_url}")
    
    # Imports inside task to avoid main thread import issues
    from main import llm, controller, browser, _hitl_client
    
    agent = Agent(
        task=task_instructions,
        llm=llm,
        controller=controller,
        browser=browser,
        max_failures=10,
        max_actions_per_step=5,
    )
    
    try:
        result = await agent.run()
        if result.is_successful():
            logger.info("✅ [TASKIQ WORKER] Agent task completed successfully.")
            if _hitl_client:
                _hitl_client.update_state("COMPLETED", "Task completed successfully!")
            return result.final_result() or "Success with no final output."
        else:
            logger.warning("⚠️ [TASKIQ WORKER] Agent task failed or stopped.")
            if _hitl_client:
                _hitl_client.update_state("COMPLETED", "Task finished (may not have fully succeeded).")
            return "Task failed or was stopped."
    except Exception as e:
        logger.error(f"❌ [TASKIQ WORKER] Fatal error in agent execution: {e}")
        if _hitl_client:
            _hitl_client.update_state("ERROR", f"Fatal error: {e}")
        raise e
