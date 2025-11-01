# handlers/schedule.py — FINAL, KILLER VERSION — AUTO-CREATES USER FIRST
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loader import dp
from db.session import AsyncSessionLocal
from db.models import User, Batch, Schedule, ScheduleType, schedule_batch_association
from sqlalchemy import select, update, delete
from keyboard.inline import get_batch_keyboard, get_schedule_type_keyboard
from config import SUPER_ADMIN_ID
from datetime import datetime
import logging
import calendar
import asyncio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# FSM STATES
# ----------------------------------------------------------------------
class ScheduleStates(StatesGroup):
    choosing_batches = State()
    choosing_type = State()
    choosing_date = State()
    choosing_time = State()
    entering_message = State()
    confirming = State()


# ----------------------------------------------------------------------
# AUTO-CREATE USER + ADMIN CHECK — CALLED FIRST
# ----------------------------------------------------------------------
async def ensure_user_exists(user_id: int, username: str | None = None) -> bool:
    """Create user if not exists. Return True if admin or super admin."""
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                is_admin = (user_id == SUPER_ADMIN_ID)
                new_user = User(
                    user_id=user_id,
                    username=username,
                    is_admin=is_admin
                )
                session.add(new_user)
                await session.commit()
                logger.info(f"USER CREATED: {user_id} | Admin: {is_admin}")
                return is_admin
            else:
                is_admin = user.is_admin or (user_id == SUPER_ADMIN_ID)
                logger.info(f"USER EXISTS: {user_id} | Admin: {is_admin}")
                return is_admin
        except Exception as e:
            logger.error(f"USER CHECK FAILED: {e}")
            return False


# ----------------------------------------------------------------------
# CALENDAR
# ----------------------------------------------------------------------
def create_calendar(year: int | None = None, month: int | None = None):
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    inline = []
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    prev = types.InlineKeyboardButton(text="<<", callback_data=f"cal_prev_{year}_{month}")
    nxt = types.InlineKeyboardButton(text=">>", callback_data=f"cal_next_{year}_{month}")
    title = types.InlineKeyboardButton(text=f"{month_names[month - 1]} {year}", callback_data="ignore")
    inline.append([prev, title, nxt])

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    inline.append([types.InlineKeyboardButton(text=d, callback_data="ignore") for d in days])

    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(types.InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                txt = f"*{day}" if datetime(year, month, day).date() == now.date() else str(day)
                row.append(types.InlineKeyboardButton(text=txt, callback_data=f"cal_day_{year}_{month}_{day}"))
        inline.append(row)

    return types.InlineKeyboardMarkup(inline_keyboard=inline)


# ----------------------------------------------------------------------
# TIME PICKER
# ----------------------------------------------------------------------
def create_time_picker():
    inline = []
    row = []
    for h in range(24):
        btn = types.InlineKeyboardButton(text=f"{h:02d}:00", callback_data=f"time_{h}")
        row.append(btn)
        if len(row) == 6:
            inline.append(row)
            row = []
    if row:
        inline.append(row)
    return types.InlineKeyboardMarkup(inline_keyboard=inline)


# ----------------------------------------------------------------------
# /schedule
# ----------------------------------------------------------------------
@dp.message(Command("schedule"))
async def cmd_schedule(message: types.Message, state: FSMContext):
    if not await ensure_user_exists(message.from_user.id, message.from_user.username):
        await message.answer("No permission.")
        return

    async with AsyncSessionLocal() as session:
        batches = (await session.execute(select(Batch))).scalars().all()

    if not batches:
        await message.answer("No batches found.")
        return

    await message.answer("Select batches:", reply_markup=get_batch_keyboard(batches))
    await state.set_state(ScheduleStates.choosing_batches)


# ----------------------------------------------------------------------
# BATCH SELECTION
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("batch_"))
async def process_batch(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_user_exists(callback.from_user.id, callback.from_user.username):
        await callback.answer("No permission.", show_alert=True)
        return

    batch_id = int(callback.data.split("_")[1])
    data = await state.get_data()
    selected = data.get("batches", [])
    if batch_id in selected:
        selected.remove(batch_id)
    else:
        selected.append(batch_id)
    await state.update_data(batches=selected)

    async with AsyncSessionLocal() as session:
        batches = (await session.execute(select(Batch))).scalars().all()

    await callback.message.edit_reply_markup(reply_markup=get_batch_keyboard(batches, selected))


@dp.callback_query(F.data == "done_batches")
async def done_batches(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_user_exists(callback.from_user.id, callback.from_user.username):
        await callback.answer("No permission.", show_alert=True)
        return

    data = await state.get_data()
    if not data.get("batches"):
        await callback.answer("Select at least one batch.", show_alert=True)
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Choose type:", reply_markup=get_schedule_type_keyboard())
    await state.set_state(ScheduleStates.choosing_type)


# ----------------------------------------------------------------------
# TYPE → CALENDAR
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("type_"))
async def process_type(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_user_exists(callback.from_user.id, callback.from_user.username):
        await callback.answer("No permission.", show_alert=True)
        return

    type_map = {
        "type_weekly": ScheduleType.WEEKLY,
        "type_monthly": ScheduleType.MONTHLY,
        "type_custom": ScheduleType.CUSTOM,
    }
    sched_type = type_map[callback.data]
    await state.update_data(schedule_type=sched_type)

    await callback.message.edit_reply_markup(reply_markup=None)

    now = datetime.utcnow()
    await callback.message.answer("Pick first send date:", reply_markup=create_calendar(now.year, now.month))
    await state.update_data(current_year=now.year, current_month=now.month)
    await state.set_state(ScheduleStates.choosing_date)


# ----------------------------------------------------------------------
# CALENDAR NAV
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("cal_prev_"))
@dp.callback_query(F.data.startswith("cal_next_"))
async def navigate_calendar(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_user_exists(callback.from_user.id, callback.from_user.username):
        await callback.answer("No permission.", show_alert=True)
        return

    parts = callback.data.split("_")
    action = parts[1]
    year, month = int(parts[2]), int(parts[3])

    if action == "prev":
        year -= 1
    else:
        year += 1

    await callback.message.edit_reply_markup(reply_markup=create_calendar(year, month))
    await state.update_data(current_year=year, current_month=month)


# ----------------------------------------------------------------------
# DATE → TIME
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("cal_day_"))
async def select_date(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_user_exists(callback.from_user.id, callback.from_user.username):
        await callback.answer("No permission.", show_alert=True)
        return

    _, _, year, month, day = callback.data.split("_")
    selected = datetime(int(year), int(month), int(day))

    await state.update_data(selected_date=selected.date())
    await callback.message.edit_text(
        f"Date: <b>{selected.strftime('%Y-%m-%d')}</b>\nNow pick hour (24-h):",
        reply_markup=create_time_picker(),
        parse_mode="HTML",
    )
    await state.set_state(ScheduleStates.choosing_time)


# ----------------------------------------------------------------------
# TIME → MESSAGE
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("time_"))
async def select_time(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_user_exists(callback.from_user.id, callback.from_user.username):
        await callback.answer("No permission.", show_alert=True)
        return

    hour = int(callback.data.split("_")[1])
    data = await state.get_data()
    dt = data["selected_date"]
    next_run = datetime(dt.year, dt.month, dt.day, hour)

    await state.update_data(next_run=next_run)
    await callback.message.edit_text(
        f"Send at: <b>{next_run.strftime('%Y-%m-%d %H:%M UTC')}</b>\nEnter your message:",
        parse_mode="HTML",
    )
    await state.set_state(ScheduleStates.entering_message)


# ----------------------------------------------------------------------
# MESSAGE → CONFIRM
# ----------------------------------------------------------------------
@dp.message(ScheduleStates.entering_message)
async def process_message(message: types.Message, state: FSMContext):
    if not await ensure_user_exists(message.from_user.id, message.from_user.username):
        await message.answer("No permission.")
        return

    await state.update_data(message_text=message.text)
    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        batch_names = [
            (await session.execute(select(Batch.name).where(Batch.id == bid))).scalar_one()
            for bid in data["batches"]
        ]

    preview = (
        f"<b>Schedule Preview</b>\n\n"
        f"<b>Batches:</b> {', '.join(batch_names)}\n"
        f"<b>Type:</b> {data['schedule_type'].value.title()}\n"
        f"<b>Send at:</b> <code>{data['next_run'].strftime('%Y-%m-%d %H:%M UTC')}</code>\n\n"
        f"<b>Message:</b>\n<pre>{message.text}</pre>\n\n"
        f"Ready?"
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Confirm", callback_data="confirm_schedule")],
        [types.InlineKeyboardButton(text="Cancel", callback_data="cancel_schedule")]
    ])

    await message.answer(preview, reply_markup=kb, parse_mode="HTML")
    await state.set_state(ScheduleStates.confirming)


# ----------------------------------------------------------------------
# SAVE SCHEDULE — USER EXISTS FIRST
# ----------------------------------------------------------------------
async def _save_schedule(data: dict, admin_id: int) -> Schedule | None:
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        async with AsyncSessionLocal() as session:
            try:
                sched = Schedule(
                    message=data["message_text"],
                    type=data["schedule_type"],
                    cron_expr=None,
                    next_run=data["next_run"],
                    admin_id=admin_id,
                    is_active=True,
                )
                session.add(sched)
                await session.flush()
                logger.info(f"SCHEDULE #{sched.id} CREATED")

                for bid in data["batches"]:
                    stmt = schedule_batch_association.insert().values(
                        schedule_id=sched.id, batch_id=bid
                    )
                    await session.execute(stmt)

                await session.commit()
                logger.info(f"SCHEDULE #{sched.id} SAVED + LINKED")
                return sched

            except Exception as e:
                await session.rollback()
                logger.error(f"Save attempt {attempt} failed: {e}")
                if attempt == max_retries:
                    return None
                await asyncio.sleep(1)

    return None


# ----------------------------------------------------------------------
# CONFIRM — USER CREATED FIRST
# ----------------------------------------------------------------------
@dp.callback_query(F.data == "confirm_schedule")
async def confirm_schedule(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    username = callback.from_user.username

    # USER MUST EXIST BEFORE SAVE
    if not await ensure_user_exists(user_id, username):
        await callback.answer("No permission.", show_alert=True)
        return

    data = await state.get_data()
    saved = await _save_schedule(data, user_id)

    if not saved:
        await callback.message.edit_text("Failed to save schedule – check logs.")
        return

    await callback.message.edit_text(
        f"Schedule <b>#{saved.id}</b> created!\n"
        f"Send at: <b>{saved.next_run.strftime('%Y-%m-%d %H:%M UTC')}</b>\n"
        f"Type: <b>{saved.type.value.title()}</b>",
        parse_mode="HTML",
    )
    await state.clear()


@dp.callback_query(F.data == "cancel_schedule")
async def cancel_schedule(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Cancelled.")
    await state.clear()


# ----------------------------------------------------------------------
# ADMIN COMMANDS
# ----------------------------------------------------------------------
@dp.message(Command("list_schedules"))
async def cmd_list_schedules(message: types.Message):
    if not await ensure_user_exists(message.from_user.id, message.from_user.username):
        await message.answer("No permission.")
        return

    async with AsyncSessionLocal() as session:
        schedules = (await session.execute(select(Schedule).order_by(Schedule.id))).scalars().all()

    if not schedules:
        await message.answer("No schedules.")
        return

    lines = []
    for s in schedules:
        status = "Active" if s.is_active else "Paused"
        batch_names = ", ".join(b.name for b in s.batches) if s.batches else "None"
        lines.append(
            f"<b>#{s.id}</b> | {status}\n"
            f"Type: <code>{s.type.value}</code>\n"
            f"Batches: <code>{batch_names}</code>\n"
            f"Next: <code>{s.next_run.strftime('%Y-%m-%d %H:%M')}</code>\n"
            f"Msg: <i>{s.message[:50]}{'...' if len(s.message)>50 else ''}</i>\n"
        )
    await message.answer("<b>Active Schedules</b>\n\n" + "\n".join(lines), parse_mode="HTML")


@dp.message(Command("pause_schedule"))
async def cmd_pause_schedule(message: types.Message):
    if not await ensure_user_exists(message.from_user.id, message.from_user.username):
        await message.answer("No permission.")
        return
    try:
        sched_id = int(message.text.split(maxsplit=1)[1])
    except Exception:
        await message.answer("Usage: /pause_schedule <id>")
        return

    async with AsyncSessionLocal() as session:
        sched = (await session.execute(select(Schedule).where(Schedule.id == sched_id))).scalar_one_or_none()
        if not sched:
            await message.answer("Schedule not found.")
            return
        if not sched.is_active:
            await message.answer("Already paused.")
            return
        await session.execute(update(Schedule).where(Schedule.id == sched_id).values(is_active=False))
        await session.commit()
        await message.answer(f"Schedule <b>#{sched_id}</b> paused.", parse_mode="HTML")


@dp.message(Command("resume_schedule"))
async def cmd_resume_schedule(message: types.Message):
    if not await ensure_user_exists(message.from_user.id, message.from_user.username):
        await message.answer("No permission.")
        return
    try:
        sched_id = int(message.text.split(maxsplit=1)[1])
    except Exception:
        await message.answer("Usage: /resume_schedule <id>")
        return

    async with AsyncSessionLocal() as session:
        sched = (await session.execute(select(Schedule).where(Schedule.id == sched_id))).scalar_one_or_none()
        if not sched:
            await message.answer("Schedule not found.")
            return
        if sched.is_active:
            await message.answer("Already active.")
            return
        await session.execute(update(Schedule).where(Schedule.id == sched_id).values(is_active=True))
        await session.commit()
        await message.answer(f"Schedule <b>#{sched_id}</b> resumed.", parse_mode="HTML")


@dp.message(Command("delete_schedule"))
async def cmd_delete_schedule(message: types.Message):
    if not await ensure_user_exists(message.from_user.id, message.from_user.username):
        await message.answer("No permission.")
        return
    try:
        sched_id = int(message.text.split(maxsplit=1)[1])
    except Exception:
        await message.answer("Usage: /delete_schedule <id>")
        return

    async with AsyncSessionLocal() as session:
        sched = (await session.execute(select(Schedule).where(Schedule.id == sched_id))).scalar_one_or_none()
        if not sched:
            await message.answer("Schedule not found.")
            return
        await session.execute(delete(Schedule).where(Schedule.id == sched_id))
        await session.commit()
        await message.answer(f"Schedule <b>#{sched_id}</b> deleted forever.", parse_mode="HTML")