# Pipeline Support in Modules

← [Index](../../API_DOC.md)

Pipeline allows chaining commands with `|` (pipe) operator. Each command's output becomes the next command's input.

## Basic Concepts

| Attribute | Description |
|-----------|-------------|
| `event.piped` | `True` if command is part of a pipe chain |
| `event.pipe_input` | Text output from the previous command |
| `event.pipe_output` | Set this to pass output to next command |
| `event.pipe_exit_code` | Set to `1` on error to stop pipeline |

## Detecting Pipeline Mode

```python
async def my_command(event):
    piped = getattr(event, "piped", False)
    pipe_input = getattr(event, "pipe_input", None) or ""

    if piped:
        # We're in a pipe chain, work with pipe_input
        result = process(pipe_input)
        event.pipe_output = result
    else:
        # Normal command execution
        await self.edit(event, "Hello!")
```

## Working with Pipe Input

### Simple text transformation

```python
@command("upper", doc_en="convert to uppercase")
async def cmd_upper(self, event):
    pipe_input = getattr(event, "pipe_input", None) or ""
    args = self.args_raw(event)

    # Use pipe_input if no arguments
    text = args or pipe_input

    if not text:
        await self.edit(event, self.strings("usage"), parse_mode="html")
        return

    result = text.upper()

    # Check if we're piped, pass output forward
    if getattr(event, "piped", False):
        await self.edit(event, result)
        return

    await self.edit(event, result, parse_mode="html")
```

### Using `{pipe_input}` placeholder

Commands can reference the previous output in arguments:

```python
@command("echo", doc_en="print text")
async def cmd_echo(self, event):
    args = self.args_raw(event)
    pipe_input = getattr(event, "pipe_input", None) or ""
    text = ""

    if args:
        # Replace placeholder with previous output
        text = args.replace("{pipe_input}", pipe_input)
    else:
        text = pipe_input

    event.no_add_args_to_input = True

    if not text:
        await self.edit(event, "")
        return

    # If piped, don't add formatting
    if getattr(event, "piped", False):
        await self.edit(event, text) # or event.pipe_ontput = text \n return
        return

    await self.edit(event, text, parse_mode="html")
```

## Error Handling

### Setting exit code

```python
@command("validate", doc_en="validate input")
async def cmd_validate(self, event):
    pipe_input = getattr(event, "pipe_input", None) or ""

    if not pipe_input:
        event.pipe_exit_code = 1
        await self.edit(event, "No input provided", parse_mode="html")
        return

    if not is_valid(pipe_input):
        event.pipe_exit_code = 1
        await self.edit(event, "Invalid input", parse_mode="html")
        return

    await self.edit(event, "OK", parse_mode="html")
```

### Passing error to next command

When a command fails in a pipe chain, you can preserve `pipe_input` so the next command can handle the error:

```python
@command("risky", doc_en="risky operation")
async def cmd_risky(self, event):
    pipe_input = getattr(event, "pipe_input", None) or ""

    try:
        result = process(pipe_input)
        await self.edit(event, result)
    except Exception as e:
        # Keep pipe_input for error handling in next command
        event.pipe_input = pipe_input
        event.pipe_exit_code = 1
        await self.edit(event, f"Error: {e}", parse_mode="html")
```

## Complete Example

```python
from telethon import events
from core.lib.loader.module_base import ModuleBase, command


class MyModule(ModuleBase):
    name = "mymodule"
    version = "1.0.0"
    author = "@Author"
    description = {"en": "My module with pipeline support"}

    strings = {"name": "mymodule"}

    @command(
        "reverse",
        doc_ru="[text] перевернуть текст",
        doc_en="[text] reverse text",
    )
    async def cmd_reverse(self, event: events.NewMessage.Event) -> None:
        try:
            pipe_input = getattr(event, "pipe_input", None) or ""
            args = self.args_raw(event).strip()

            text = args or pipe_input

            if not text:
                await self.edit(event, self.strings("reverse_usage"), parse_mode="html")
                return

            result = text[::-1]

            # Pass output if piped
            if getattr(event, "piped", False):
                await self.edit(event, result)
                return

            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="reverse", event=event)

    @command(
        "length",
        doc_ru="[text] длина текста",
        doc_en="[text] text length",
    )
    async def cmd_length(self, event: events.NewMessage.Event) -> None:
        try:
            pipe_input = getattr(event, "pipe_input", None) or ""
            args = self.args_raw(event).strip()

            text = args or pipe_input

            if not text:
                await self.edit(event, self.strings("length_usage"), parse_mode="html")
                return

            result = str(len(text))

            if getattr(event, "piped", False):
                await self.edit(event, result)
                return

            await self.edit(event, result, parse_mode="html")
        except Exception as e:
            await self.kernel.handle_error(e, source="length", event=event)
```

## Enabling/Disabling Pipeline

Pipeline can be enabled/disabled in settings:

```
.pipeline # Enable/Disabled pipeline (toggle command)
```

Commands work regardless of pipeline status — they just won't receive `pipe_input` when pipeline is disabled.

## Best Practices

1. **Always check both `args` and `pipe_input`** — prefer args if provided, fallback to pipe_input
2. **Check `event.piped` before formatting** — use `parse_mode="html"` only when not piped
3. **Set `event.pipe_exit_code = 1` on errors** — stops the pipeline chain
4. **Use `{pipe_input}` placeholder** — allows users to reference previous output in args
5. **Set `event.no_add_args_to_input = True`** — prevents args from being added to input
6. **Keep pipe_input on error** — allows error handling in downstream commands

## Testing Pipeline

```
.echo 123 | .upper

.echo hello world | .reverse

.t ping -c 1 1.1.1.1 | .reverse | .echo <pre>{pipe_input}</pre>
```
