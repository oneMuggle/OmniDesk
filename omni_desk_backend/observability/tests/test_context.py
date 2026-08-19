from observability.context import request_id_var


def test_request_id_var_default_is_none():
    assert request_id_var.get() is None


def test_request_id_var_set_and_reset():
    token = request_id_var.set("abc123")
    try:
        assert request_id_var.get() == "abc123"
    finally:
        request_id_var.reset(token)
    assert request_id_var.get() is None


def test_request_id_var_isolated_between_contexts():
    import asyncio

    async def child():
        request_id_var.set("child-id")
        return request_id_var.get()

    async def main():
        token = request_id_var.set("main-id")
        try:
            child_val = await asyncio.create_task(child())
            return request_id_var.get(), child_val
        finally:
            request_id_var.reset(token)

    main_val, child_val = asyncio.run(main())
    assert main_val == "main-id"
    assert child_val == "child-id"
