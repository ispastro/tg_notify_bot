# handlers/schedule.py — THE ULTIMATE FINAL VERSION — 12-HOUR + FLAWLESS LOGIC
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
import calendar
import asyncio
import logging
from sqlalchemy.orm import selectinload

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
# AUTO-CREATE USER + ADMIN CHECK
# ----------------------------------------------------------------------
async def ensure_user_exists(user_id: int, username: str | None = None) -> bool:
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                is_super = (user_id == SUPER_ADMIN_ID)
                new_user = User(
                    user_id=user_id,
                    username=username or "Unknown",
                    full_name="Admin",
                    is_admin=is_super,
                    join_date=datetime.utcnow()
                )
                session.add(new_user)
                await session.commit()
                logger.info(f"NEW USER CREATED: {user_id} | SuperAdmin: {is_super}")
                return True  # Admins always allowed

            return user.is_admin or (user_id == SUPER_ADMIN_ID)
        except Exception as e:
            logger.error(f"USER CHECK FAILED: {e}")
            return False


# ----------------------------------------------------------------------
# 12-HOUR FORMAT HELPER
# ----------------------------------------------------------------------
def format_12hour(dt: datetime) -> str:
    period = "AM" if dt.hour < 12 else "PM"
    hour = dt.hour % 12
    hour = 12 if hour == 0 else hour
    return f"{dt.strftime('%b %d, %Y')} at {hour}:00 {period} UTC"


# ----------------------------------------------------------------------
# CALENDAR (unchanged, beautiful)
# ----------------------------------------------------------------------
def create_calendar(year: int | None = None, month: int | None = None):
    now = datetime.utcnow()
    year = year or now.year
    month = month or now.month

    inline = []
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    prev = types.InlineKeyboardButton(text="Previous", callback_data=f"cal_prev_{year}_{month}")
    nxt = types.InlineKeyboardButton(text="Next", callback_data=f"cal_next_{year}_{month}")
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
# 12-HOUR TIME PICKER — BEAUTIFUL & CLEAN
# ----------------------------------------------------------------------
def create_time_picker():
    inline = []
    # AM Hours
    row = []
    for h in range(12):
        hour_12 = 12 if h == 0 else h
        text = f"{hour_12}:00 AM"
        callback = f"time_{h}"
        row.append(types.InlineKeyboardButton(text=text, callback_data=callback))
        if len(row) == 3:
            inline.append(row)
            row = []
    if row:
        inline.append(row)

    # PM Hours
    row = []
    for h in range(12, 24):
        hour_12 = h - 12
        hour_12 = 12 if hour_12 == 0 else hour_12
        text = f"{hour_12}:00 PM"
        callback = f"time_{h}"
        row.append(types.InlineKeyboardButton(text=text, callback_data=callback))
        if len(row) == 3:
            inline.append(row)
            row = []
    if row:
        inline.append(row)

    return types.InlineKeyboardMarkup(inline_keyboard=inline)


# ----------------------------------------------------------------------
# /schedule COMMAND
# ----------------------------------------------------------------------
@dp.message(Command("schedule"))
async def cmd_schedule(message: types.Message, state: FSMContext):
    if not await ensure_user_exists(message.from_user.id, message.from_user.username):
        await message.answer("You don't have permission to use this command.")
        return

    async with AsyncSessionLocal() as session:
        batches = (await session.execute(select(Batch))).scalars().all()

    if not batches:
        await message.answer("No batches found in the database.")
        return

    await message.answer("Select target batches:", reply_markup=get_batch_keyboard(batches))
    await state.set_state(ScheduleStates.choosing_batches)


# ----------------------------------------------------------------------
# BATCH SELECTION (unchanged)
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("batch_"))
async def process_batch(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_user_exists(callback.from_user.id):
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
#the done button
@dp.callback_query(F.data == "done_batches")
async def done_batches(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    data = await state.get_data()
    selected_batches = data.get("batches", [])

    if not selected_batches:
        await callback.answer("Please select at least one batch!", show_alert=True)
        return

    # Success: at least one batch selected
    await callback.answer()  # Remove loading spinner

    # Show how many batches selected + proceed
    await callback.message.edit_text(
        f"Selected batches: {len(selected_batches)}\n\nNow choose the schedule type:",
        reply_markup=get_schedule_type_keyboard()
    )

    await state.set_state(ScheduleStates.choosing_type)
# ----------------------------------------------------------------------
@dp.message(ScheduleStates.entering_message)
async def process_message(message: types.Message, state: FSMContext):
    if not await ensure_user_exists(message.from_user.id):
        await message.answer("No permission.")
        return

    await state.update_data(message_text=message.text)
    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        batch_names = [
            (await session.execute(select(Batch.name).where(Batch.id == bid))).scalar_one()
            for bid in data["batches"]
        ]

    nice_time = format_12hour(data["next_run"])

    preview = (
        f"<b>New Schedule</b>\n\n"
        f"<b>Batches:</b> {', '.join(batch_names)}\n"
        f"<b>Type:</b> {data['schedule_type'].value.title()}\n"
        f"<b>Send Time:</b> <code>{nice_time}</code>\n\n"
        f"<b>Message:</b>\n<pre>{message.text}</pre>\n\n"
        f"Send this schedule?"
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="Confirm & Send", callback_data="confirm_schedule")],
        [types.InlineKeyboardButton(text="Cancel", callback_data="cancel_schedule")]
    ])

    await message.answer(preview, reply_markup=kb, parse_mode="HTML")
    await state.set_state(ScheduleStates.confirming)


# ----------------------------------------------------------------------
# SAVE SCHEDULE
# ----------------------------------------------------------------------
async def _save_schedule(data: dict, admin_id: int) -> Schedule | None:
    async with AsyncSessionLocal() as session:
        try:
            sched = Schedule(
                message=data["message_text"],
                type=data["schedule_type"],
                next_run=data["next_run"],
                admin_id=admin_id,
                is_active=True,
            )
            session.add(sched)
            await session.flush()

            for bid in data["batches"]:
                await session.execute(
                    schedule_batch_association.insert().values(schedule_id=sched.id, batch_id=bid)
                )

            await session.commit()
            return sched
        except Exception as e:
            await session.rollback()
            logger.error(f"Schedule save failed: {e}")
            return None


# ----------------------------------------------------------------------
# CONFIRM & CANCEL
# ----------------------------------------------------------------------
@dp.callback_query(F.data == "confirm_schedule")
async def confirm_schedule(callback: types.CallbackQuery, state: FSMContext):
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    data = await state.get_data()
    saved = await _save_schedule(data, callback.from_user.id)

    if not saved:
        await callback.message.edit_text("Failed to create schedule. Try again.")
        return

    await callback.message.edit_text(
        f"Schedule <b>#{saved.id}</b> Created Successfully!\n\n"
        f"Will send: <b>{format_12hour(saved.next_run)}</b>\n"
        f"Type: <b>{saved.type.value.title()}</b>",
        parse_mode="HTML"
    )
    await state.clear()


@dp.callback_query(F.data == "cancel_schedule")
async def cancel_schedule(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Schedule cancelled.")
    await state.clear()


# ----------------------------------------------------------------------
# ADMIN: LIST SCHEDULES (12-HOUR FORMAT)
# ----------------------------------------------------------------------
@dp.message(Command("list_schedules"))
async def cmd_list_schedules(message: types.Message):
    if not await ensure_user_exists(message.from_user.id):
        await message.answer("No permission.")
        return

    async with AsyncSessionLocal() as session:
        schedules = (await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).order_by(Schedule.id)
        )).scalars().all()

    if not schedules:
        await message.answer("No active schedules.")
        return

    lines = []
    for s in schedules:
        status = "Active" if s.is_active else "Paused"
        batches = ", ".join(b.name for b in s.batches) if s.batches else "None"
        lines.append(
            f"<b>#{s.id}</b> | {status}\n"
            f"Batches: <code>{batches}</code>\n"
            f"Next: <code>{format_12hour(s.next_run)}</code>\n"
            f"Type: <code>{s.type.value}</code>\n"
            f"Preview: <i>{s.message[:60]}{'...' if len(s.message)>60 else ''}</i>\n"
        )

    await message.answer(
        f"<b>Scheduled Broadcasts ({len(schedules)})</b>\n\n" + "\n\n".join(lines),
        parse_mode="HTML"
    )


# ----------------------------------------------------------------------
# PAUSE / RESUME / DELETE (unchanged, just cleaner)
# ----------------------------------------------------------------------
@dp.message(Command("pause_schedule"))
async def cmd_pause_schedule(message: types.Message):
    if not await ensure_user_exists(message.from_user.id): return await message.answer("No permission.")
    try:
        sched_id = int(message.text.split(maxsplit=1)[1])
        async with AsyncSessionLocal() as session:
            await session.execute(update(Schedule).where(Schedule.id == sched_id).values(is_active=False))
            await session.commit()
        await message.answer(f"Schedule <b>#{sched_id}</b> paused.", parse_mode="HTML")
    except: await message.answer("Usage: /pause_schedule <id>")


@dp.message(Command("resume_schedule"))
async def cmd_resume_schedule(message: types.Message):
    if not await ensure_user_exists(message.from_user.id): return await message.answer("No permission.")
    try:
        sched_id = int(message.text.split(maxsplit=1)[1])
        async with AsyncSessionLocal() as session:
            await session.execute(update(Schedule).where(Schedule.id == sched_id).values(is_active=True))
            await session.commit()
        await message.answer(f"Schedule <b>#{sched_id}</b> resumed.", parse_mode="HTML")
    except: await message.answer("Usage: /resume_schedule <id>")


@dp.message(Command("delete_schedule"))
async def cmd_delete_schedule(message: types.Message):
    if not await ensure_user_exists(message.from_user.id): return await message.answer("No permission.")
    try:
        sched_id = int(message.text.split(maxsplit=1)[1])
        async with AsyncSessionLocal() as session:
            await session.execute(delete(Schedule).where(Schedule.id == sched_id))
            await session.commit()
        await message.answer(f"Schedule <b>#{sched_id}</b> deleted permanently.", parse_mode="HTML")
    except: await message.answer("Usage: /delete_schedule <id>")