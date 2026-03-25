# author: @kozhura_ubezhishe_player_fly
# version: 2.0.0
# description: калькулятор с инлайн-кнопками — нажимай кнопки прямо в чате

import math
import ast
import operator
import re
import logging

from telethon import Button

logger = logging.getLogger(__name__)


def register(kernel):
    client = kernel.client

    # Хранилище состояний калькуляторов {message_id: {"expression": str, "result": str, "history": str}}
    calc_sessions = {}

    SAFE_OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    SAFE_FUNCTIONS = {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "sqrt": math.sqrt,
        "log": math.log,
        "log10": math.log10,
        "abs": abs,
        "ceil": math.ceil,
        "floor": math.floor,
        "round": round,
        "exp": math.exp,
        "asin": math.asin,
        "acos": math.acos,
        "atan": math.atan,
    }

    SAFE_CONSTANTS = {
        "pi": math.pi,
        "e": math.e,
        "tau": math.tau,
    }

    def safe_eval_node(node):
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError("bad const")

        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type not in SAFE_OPERATORS:
                raise ValueError("bad op")
            return SAFE_OPERATORS[op_type](safe_eval_node(node.operand))

        elif isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in SAFE_OPERATORS:
                raise ValueError("bad op")
            left = safe_eval_node(node.left)
            right = safe_eval_node(node.right)
            if (
                op_type == ast.Pow
                and isinstance(right, (int, float))
                and abs(right) > 10000
            ):
                raise ValueError("too big power")
            return SAFE_OPERATORS[op_type](left, right)

        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ValueError("bad call")
            func_name = node.func.id.lower()
            if func_name not in SAFE_FUNCTIONS:
                raise ValueError(f"unknown func: {func_name}")
            args = [safe_eval_node(arg) for arg in node.args]
            return SAFE_FUNCTIONS[func_name](*args)

        elif isinstance(node, ast.Name):
            name = node.id.lower()
            if name in SAFE_CONSTANTS:
                return SAFE_CONSTANTS[name]
            raise ValueError(f"unknown var: {node.id}")

        raise ValueError("bad expression")

    def safe_eval(expression):
        expr = expression.strip()
        expr = expr.replace("^", "**")
        expr = expr.replace("×", "*")
        expr = expr.replace("÷", "/")
        expr = expr.replace("π", "pi")

        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            raise ValueError("синтаксическая ошибка")

        return safe_eval_node(tree.body)

    def format_result(result):
        if isinstance(result, float):
            if math.isinf(result):
                return "∞"
            if math.isnan(result):
                return "NaN"
            if result == int(result) and abs(result) < 1e15:
                return str(int(result))
            return f"{result:.10g}"
        return str(result)

    def get_display(session):
        expr = session.get("expression", "") or "0"
        history = session.get("history", "")
        result = session.get("result", "")

        display = "🧮 <b>Калькулятор | calc</b>\n\n"

        if history:
            display += f"<code>{history}</code>\n"

        if result:
            display += f"<pre>{expr}</pre>\n"
            display += "━━━━━━━━━━━━━━\n"
            display += f"<pre>= {result}</pre>"
        else:
            display += f"<pre>{expr or '0'}</pre>\n"
            display += "━━━━━━━━━━━━━━\n"
            display += "<b>= ...</b>"

        return display

    def get_keyboard(page="main"):

        if page == "main":
            return [
                [
                    Button.inline("C", b"calc:clear"),
                    Button.inline("⌫", b"calc:backspace"),
                    Button.inline("(", b"calc:input:("),
                    Button.inline(")", b"calc:input:)"),
                ],
                [
                    Button.inline("7", b"calc:input:7"),
                    Button.inline("8", b"calc:input:8"),
                    Button.inline("9", b"calc:input:9"),
                    Button.inline("÷", b"calc:input:/"),
                ],
                [
                    Button.inline("4", b"calc:input:4"),
                    Button.inline("5", b"calc:input:5"),
                    Button.inline("6", b"calc:input:6"),
                    Button.inline("×", b"calc:input:*"),
                ],
                [
                    Button.inline("1", b"calc:input:1"),
                    Button.inline("2", b"calc:input:2"),
                    Button.inline("3", b"calc:input:3"),
                    Button.inline("−", b"calc:input:-"),
                ],
                [
                    Button.inline("0", b"calc:input:0"),
                    Button.inline(".", b"calc:input:."),
                    Button.inline("=", b"calc:equals"),
                    Button.inline("+", b"calc:input:+"),
                ],
                [
                    Button.inline("x²", b"calc:input:**2"),
                    Button.inline("xⁿ", b"calc:input:**"),
                    Button.inline("±", b"calc:negate"),
                    Button.inline("f(x)", b"calc:functions"),
                ],
                [
                    Button.inline("❌ Закрыть", b"calc:close"),
                ],
            ]

        elif page == "functions":
            return [
                [
                    Button.inline("sin", b"calc:func:sin("),
                    Button.inline("cos", b"calc:func:cos("),
                    Button.inline("tan", b"calc:func:tan("),
                ],
                [
                    Button.inline("√", b"calc:func:sqrt("),
                    Button.inline("log", b"calc:func:log("),
                    Button.inline("log₁₀", b"calc:func:log10("),
                ],
                [
                    Button.inline("asin", b"calc:func:asin("),
                    Button.inline("acos", b"calc:func:acos("),
                    Button.inline("atan", b"calc:func:atan("),
                ],
                [
                    Button.inline("π", b"calc:input:pi"),
                    Button.inline("e", b"calc:input:e"),
                    Button.inline("τ", b"calc:input:tau"),
                ],
                [
                    Button.inline("abs", b"calc:func:abs("),
                    Button.inline("ceil", b"calc:func:ceil("),
                    Button.inline("floor", b"calc:func:floor("),
                ],
                [
                    Button.inline("exp", b"calc:func:exp("),
                    Button.inline("round", b"calc:func:round("),
                    Button.inline("%", b"calc:input:%"),
                ],
                [
                    Button.inline("⬅️ Назад", b"calc:mainpage"),
                ],
            ]

    def get_session(msg_id):
        """Получает или создаёт сессию"""
        if msg_id not in calc_sessions:
            calc_sessions[msg_id] = {
                "expression": "",
                "result": "",
                "history": "",
                "just_evaluated": False,
            }
        return calc_sessions[msg_id]

    @kernel.register.command("calc")
    # открыть калькулятор с кнопками: .calc
    async def calc_cmd(event):
        try:
            session = {
                "expression": "",
                "result": "",
                "history": "",
                "just_evaluated": False,
            }

            display = get_display(session)
            keyboard = get_keyboard("main")

            true, msg = await kernel.inline_form(
                event.chat_id, display, buttons=keyboard
            )
            calc_sessions[event.id] = session
            if true:
                await event.delete()

        except Exception as e:
            await kernel.handle_error(e, source="calc_cmd", event=event)

    async def calc_callback(event):
        try:
            msg_id = event.message_id
            session = get_session(msg_id)
            data = event.data.decode("utf-8")

            parts = data.split(":", 2)
            action = parts[1] if len(parts) > 1 else ""
            value = parts[2] if len(parts) > 2 else ""

            if action == "input":
                if session["just_evaluated"]:
                    if value and value[0].isdigit():
                        session["history"] = (
                            f"{session['expression']} = {session['result']}"
                        )
                        session["expression"] = ""
                        session["result"] = ""
                    session["just_evaluated"] = False

                session["expression"] += value
                session["result"] = ""

                try:
                    expr = session["expression"]
                    open_parens = expr.count("(") - expr.count(")")
                    test_expr = expr + ")" * max(0, open_parens)

                    if test_expr and test_expr[-1] not in "+-*/(^.":
                        result = safe_eval(test_expr)
                        session["result"] = format_result(result)
                except:
                    session["result"] = ""

            elif action == "func":
                if session["just_evaluated"]:
                    session["expression"] = f"{value}{session['result']})"
                    session["just_evaluated"] = False
                else:
                    session["expression"] += value

                session["result"] = ""

                try:
                    expr = session["expression"]
                    open_parens = expr.count("(") - expr.count(")")
                    test_expr = expr + ")" * max(0, open_parens)
                    if test_expr and test_expr[-1] not in "+-*/(^.":
                        result = safe_eval(test_expr)
                        session["result"] = format_result(result)
                except:
                    session["result"] = ""

            elif action == "equals":
                if session["expression"]:
                    try:
                        expr = session["expression"]
                        open_parens = expr.count("(") - expr.count(")")
                        if open_parens > 0:
                            expr += ")" * open_parens
                            session["expression"] = expr

                        result = safe_eval(expr)
                        session["result"] = format_result(result)
                        session["just_evaluated"] = True

                    except ValueError as e:
                        session["result"] = f"❌ {str(e)}"
                    except ZeroDivisionError:
                        session["result"] = "❌ ÷ 0"
                    except OverflowError:
                        session["result"] = "❌ overflow"
                    except Exception:
                        session["result"] = "❌ ошибка"

            elif action == "clear":
                session["expression"] = ""
                session["result"] = ""
                session["history"] = ""
                session["just_evaluated"] = False

            elif action == "backspace":
                if session["just_evaluated"]:
                    session["just_evaluated"] = False

                expr = session["expression"]
                if expr:
                    func_match = re.search(
                        r"(sin|cos|tan|sqrt|log10|log|abs|ceil|floor|exp|round|asin|acos|atan)\($",
                        expr,
                    )
                    if func_match:
                        session["expression"] = expr[: func_match.start()]
                    else:
                        session["expression"] = expr[:-1]

                session["result"] = ""

                try:
                    expr = session["expression"]
                    if expr:
                        open_parens = expr.count("(") - expr.count(")")
                        test_expr = expr + ")" * max(0, open_parens)
                        if test_expr and test_expr[-1] not in "+-*/(^.":
                            result = safe_eval(test_expr)
                            session["result"] = format_result(result)
                except:
                    pass

            elif action == "negate":
                expr = session["expression"]
                if session["just_evaluated"] and session["result"]:
                    try:
                        val = float(session["result"])
                        val = -val
                        session["result"] = format_result(val)
                        session["expression"] = session["result"]
                        session["just_evaluated"] = False
                    except:
                        pass
                elif expr:
                    if expr.startswith("-"):
                        session["expression"] = expr[1:]
                    elif expr.startswith("(-"):
                        session["expression"] = expr[2:]
                        if session["expression"].endswith(")"):
                            session["expression"] = session["expression"][:-1]
                    else:
                        session["expression"] = f"(-{expr})"

            elif action == "functions":
                display = get_display(session)
                keyboard = get_keyboard("functions")
                await event.edit(display, parse_mode="html", buttons=keyboard)
                return

            elif action == "mainpage":
                display = get_display(session)
                keyboard = get_keyboard("main")
                await event.edit(display, parse_mode="html", buttons=keyboard)
                return

            elif action == "close":
                expr = session.get("expression", "")
                result = session.get("result", "")

                if expr and result:
                    await event.edit(
                        f"🧮 <code>{expr}</code> = <b>{result}</b>", parse_mode="html"
                    )
                else:
                    await kernel.client.delete_messages(event.chat_id, [msg_id])

                if msg_id in calc_sessions:
                    del calc_sessions[msg_id]
                return

            display = get_display(session)
            keyboard = get_keyboard("main")

            try:
                await event.edit(display, parse_mode="html", buttons=keyboard)
            except Exception:
                pass

        except Exception as e:
            logger.error(f"calc callback error: {e}")
            try:
                await event.answer(f"❌ ошибка: {str(e)[:100]}")
            except:
                pass

    kernel.register_callback_handler(b"calc", calc_callback)
