# handlers/schedule/edit.py
"""Schedule editing operations (message, time, batches, type)."""
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from datetime import datetime
from loader import dp
from db.session import AsyncSessionLocal
from db.models import Schedule, Batch, ScheduleType, schedule_batch_association
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from keyboard.inline import (
    get_edit_options_keyboard,
    get_cancel_keyboard,
    get_edit_batch_keyboard,
    get_schedule_actions_keyboard,
    get_schedule_type_keyboard,
)
from .states import EditScheduleStates
from .helpers import ensure_user_exists, format_12hour
from .ui import create_calendar, create_time_picker
import logging

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# SHOW EDIT MENU
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("sched_edit_"))
async def handle_show_edit_menu(callback: types.CallbackQuery, state: FSMContext):
    """Show edit options for a schedule."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        sched = await session.get(Schedule, schedule_id)
        if not sched:
            await callback.answer("Schedule not found!", show_alert=True)
            return

    await callback.message.edit_text(
        f"✏️ <b>Edit Schedule #{schedule_id}</b>\n\n"
        f"What would you like to edit?",
        reply_markup=get_edit_options_keyboard(schedule_id),
        parse_mode="HTML"
    )
    await callback.answer()


# ----------------------------------------------------------------------
# EDIT MESSAGE FLOW
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("edit_msg_"))
async def handle_edit_message_start(callback: types.CallbackQuery, state: FSMContext):
    """Start editing message content."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        sched = await session.get(Schedule, schedule_id)
        if not sched:
            await callback.answer("Schedule not found!", show_alert=True)
            return

    await state.update_data(editing_schedule_id=schedule_id)
    await state.set_state(EditScheduleStates.editing_message)

    await callback.message.edit_text(
        f"📝 <b>Edit Message for Schedule #{schedule_id}</b>\n\n"
        f"<b>Current message:</b>\n<blockquote>{sched.message[:500]}</blockquote>\n\n"
        f"Send the new message:",
        reply_markup=get_cancel_keyboard(schedule_id),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message(EditScheduleStates.editing_message)
async def process_edit_message(message: types.Message, state: FSMContext):
    """Process new message content."""
    if not await ensure_user_exists(message.from_user.id):
        await message.answer("No permission.")
        return

    data = await state.get_data()
    schedule_id = data.get("editing_schedule_id")
    
    if not schedule_id:
        await message.answer("Error: No schedule selected.")
        await state.clear()
        return

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Schedule).where(Schedule.id == schedule_id).values(message=message.text)
        )
        await session.commit()
        
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one_or_none()

    await state.clear()
    
    if not sched:
        await message.answer("Schedule not found after update.")
        return

    logger.info(f"Schedule #{schedule_id} message updated by admin {message.from_user.id}")

    status = "🟢 Active" if sched.is_active else "⏸️ Paused"
    batches = ", ".join(b.name for b in sched.batches) if sched.batches else "None"
    next_run_str = format_12hour(sched.next_run) if sched.next_run else "Not scheduled"

    await message.answer(
        f"✅ <b>Message Updated!</b>\n\n"
        f"📅 <b>Schedule #{sched.id}</b>\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Batches:</b> {batches}\n"
        f"<b>Next Run:</b> <code>{next_run_str}</code>\n\n"
        f"<b>New Message:</b>\n<blockquote>{sched.message[:200]}{'...' if len(sched.message) > 200 else ''}</blockquote>",
        reply_markup=get_schedule_actions_keyboard(sched.id, sched.is_active),
        parse_mode="HTML"
    )


# ----------------------------------------------------------------------
# EDIT TIME FLOW
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("edit_time_"))
async def handle_edit_time_start(callback: types.CallbackQuery, state: FSMContext):
    """Start editing schedule time."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        sched = await session.get(Schedule, schedule_id)
        if not sched:
            await callback.answer("Schedule not found!", show_alert=True)
            return

    await state.update_data(editing_schedule_id=schedule_id, editing_schedule_type=sched.type)
    await state.set_state(EditScheduleStates.editing_date)

    current_time = format_12hour(sched.next_run) if sched.next_run else "Not set"
    
    await callback.message.edit_text(
        f"🕐 <b>Edit Time for Schedule #{schedule_id}</b>\n\n"
        f"<b>Current:</b> <code>{current_time}</code>\n\n"
        f"Select new date:",
        reply_markup=create_calendar(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_cal_day_"), EditScheduleStates.editing_date)
async def handle_edit_calendar_day(callback: types.CallbackQuery, state: FSMContext):
    """Handle date selection during edit."""
    parts = callback.data.split("_")
    year, month, day = int(parts[3]), int(parts[4]), int(parts[5])
    selected_date = datetime(year, month, day)

    if selected_date.date() < datetime.utcnow().date():
        await callback.answer("Cannot select a past date!", show_alert=True)
        return

    await state.update_data(editing_selected_date=selected_date)
    await state.set_state(EditScheduleStates.editing_time)

    data = await state.get_data()
    schedule_id = data.get("editing_schedule_id")

    await callback.message.edit_text(
        f"🕐 <b>Edit Time for Schedule #{schedule_id}</b>\n\n"
        f"<b>Date:</b> {selected_date.strftime('%b %d, %Y')}\n\n"
        f"Select time:",
        reply_markup=create_time_picker(),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_time_hour_"), EditScheduleStates.editing_time)
async def handle_edit_time_hour(callback: types.CallbackQuery, state: FSMContext):
    """Handle time selection during edit."""
    hour = int(callback.data.split("_")[3])
    data = await state.get_data()
    selected_date = data.get("editing_selected_date")
    schedule_id = data.get("editing_schedule_id")

    if not selected_date or not schedule_id:
        await callback.answer("Error: Missing data", show_alert=True)
        await state.clear()
        return

    next_run = selected_date.replace(hour=hour, minute=0, second=0, microsecond=0)

    if next_run <= datetime.utcnow():
        await callback.answer("Cannot schedule in the past!", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        values = {"next_run": next_run}
        if data.get("editing_new_type"):
            values["type"] = data["editing_new_type"]
            values["cron_expr"] = None  # Clear cron if switching to fixed time

        await session.execute(
            update(Schedule).where(Schedule.id == schedule_id).values(**values)
        )
        await session.commit()
        
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one()

    await state.clear()
    
    logger.info(f"Schedule #{schedule_id} time updated to {next_run} by admin {callback.from_user.id}")

    await callback.message.edit_text(
        f"✅ <b>Time Updated!</b>\n\n"
        f"📅 <b>Schedule #{sched.id}</b>\n"
        f"<b>New Time:</b> <code>{format_12hour(next_run)}</code>\n"
        f"<b>Type:</b> {sched.type.value.title()}",
        reply_markup=get_schedule_actions_keyboard(sched.id, sched.is_active),
        parse_mode="HTML"
    )
    await callback.answer()


# ----------------------------------------------------------------------
# EDIT BATCHES FLOW
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("edit_batches_"))
async def handle_edit_batches_start(callback: types.CallbackQuery, state: FSMContext):
    """Start editing schedule batches."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one_or_none()
        
        if not sched:
            await callback.answer("Schedule not found!", show_alert=True)
            return
        
        all_batches = (await session.execute(select(Batch))).scalars().all()
        current_batch_ids = [b.id for b in sched.batches]

    await state.update_data(
        editing_schedule_id=schedule_id, 
        editing_batch_ids=current_batch_ids.copy()
    )
    await state.set_state(EditScheduleStates.editing_batches)

    await callback.message.edit_text(
        f"📦 <b>Edit Batches for Schedule #{schedule_id}</b>\n\n"
        f"Select/deselect batches:",
        reply_markup=get_edit_batch_keyboard(all_batches, current_batch_ids, schedule_id),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_batch_sel_"))
async def handle_edit_batch_toggle(callback: types.CallbackQuery, state: FSMContext):
    """Toggle batch selection during edit."""
    parts = callback.data.split("_")
    schedule_id = int(parts[3])
    batch_id = int(parts[4])
    
    data = await state.get_data()
    selected = data.get("editing_batch_ids", [])
    
    if batch_id in selected:
        selected.remove(batch_id)
    else:
        selected.append(batch_id)
    
    await state.update_data(editing_batch_ids=selected)

    async with AsyncSessionLocal() as session:
        all_batches = (await session.execute(select(Batch))).scalars().all()

    await callback.message.edit_reply_markup(
        reply_markup=get_edit_batch_keyboard(all_batches, selected, schedule_id)
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_batch_save_"))
async def handle_edit_batch_save(callback: types.CallbackQuery, state: FSMContext):
    """Save batch changes."""
    schedule_id = int(callback.data.split("_")[3])
    data = await state.get_data()
    selected_batch_ids = data.get("editing_batch_ids", [])

    if not selected_batch_ids:
        await callback.answer("Please select at least one batch!", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        # Remove existing associations
        await session.execute(
            delete(schedule_batch_association).where(
                schedule_batch_association.c.schedule_id == schedule_id
            )
        )
        
        # Add new associations
        for bid in selected_batch_ids:
            await session.execute(
                schedule_batch_association.insert().values(schedule_id=schedule_id, batch_id=bid)
            )
        
        await session.commit()
        
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one()

    await state.clear()
    
    logger.info(f"Schedule #{schedule_id} batches updated by admin {callback.from_user.id}")

    batches = ", ".join(b.name for b in sched.batches)
    
    await callback.message.edit_text(
        f"✅ <b>Batches Updated!</b>\n\n"
        f"📅 <b>Schedule #{sched.id}</b>\n"
        f"<b>New Batches:</b> {batches}",
        reply_markup=get_schedule_actions_keyboard(sched.id, sched.is_active),
        parse_mode="HTML"
    )
    await callback.answer()


# ----------------------------------------------------------------------
# EDIT TYPE FLOW
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("edit_type_"))
async def handle_edit_type_start(callback: types.CallbackQuery, state: FSMContext):
    """Start editing schedule type."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        sched = await session.get(Schedule, schedule_id)
        if not sched:
            await callback.answer("Schedule not found!", show_alert=True)
            return

    await state.update_data(editing_schedule_id=schedule_id)
    await state.set_state(EditScheduleStates.editing_type)

    await callback.message.edit_text(
        f"📅 <b>Edit Type for Schedule #{schedule_id}</b>\n\n"
        f"Current Type: <b>{sched.type.value.title()}</b>\n\n"
        f"Select new schedule type:",
        reply_markup=get_schedule_type_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


# ----------------------------------------------------------------------
# HANDLE TYPE SELECTION DURING EDIT (from create.py)
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("type_"), EditScheduleStates.editing_type)
async def process_edit_schedule_type(callback: types.CallbackQuery, state: FSMContext):
    """Handle schedule type selection during edit."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    type_map = {
        "type_weekly": ScheduleType.WEEKLY,
        "type_monthly": ScheduleType.MONTHLY,
        "type_custom": ScheduleType.CUSTOM,
    }

    schedule_type = type_map.get(callback.data)
    if not schedule_type:
        await callback.answer("Invalid type!", show_alert=True)
        return

    await state.update_data(editing_new_type=schedule_type)
    
    if schedule_type == ScheduleType.CUSTOM:
        await callback.message.edit_text(
            "📅 <b>Edit Type: Custom</b>\n\n"
            "Enter your schedule in this format:\n"
            "<code>MINUTE HOUR DAY MONTH WEEKDAY</code>\n\n"
            "<b>Examples:</b>\n"
            "• <code>30 14 * * 1</code> = Every Monday at 2:30 PM\n"
            "• <code>0 9 15 * *</code> = 15th of every month at 9:00 AM\n"
            "• <code>45 18 * * 5</code> = Every Friday at 6:45 PM\n\n"
            "<b>Tips:</b>\n"
            "• Use <code>*</code> for \"any\"\n"
            "• Weekday: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat",
            reply_markup=get_cancel_keyboard(0),
            parse_mode="HTML"
        )
        await state.set_state(EditScheduleStates.editing_cron)
    else:
        await callback.message.edit_text(
            f"📅 <b>Edit Type: {schedule_type.value.title()}</b>\n\n"
            "Select the new start date:",
            reply_markup=create_calendar(),
            parse_mode="HTML"
        )
        await state.set_state(EditScheduleStates.editing_date)
    
    await callback.answer()


@dp.message(EditScheduleStates.editing_cron)
async def process_edit_cron(message: types.Message, state: FSMContext):
    """Process new cron expression."""
    if not await ensure_user_exists(message.from_user.id):
        await message.answer("No permission.")
        return

    data = await state.get_data()
    schedule_id = data.get("editing_schedule_id")
    new_type = data.get("editing_new_type")

    if not schedule_id or new_type != ScheduleType.CUSTOM:
        await message.answer("Error: Invalid state.")
        await state.clear()
        return

    # Validate cron
    import croniter
    try:
        cron = croniter.croniter(message.text.strip(), datetime.utcnow())
        next_run = cron.get_next(datetime)
    except Exception as e:
        await message.answer(
            f"❌ <b>Invalid Cron Expression</b>\n\nChecking: <code>{message.text}</code>\nError: {e}\n\n"
            "Please try again or click /cancel.",
            parse_mode="HTML"
        )
        return

    async with AsyncSessionLocal() as session:
        await session.execute(
            update(Schedule).where(Schedule.id == schedule_id).values(
                type=new_type,
                cron_expr=message.text.strip(),
                next_run=next_run
            )
        )
        await session.commit()
        
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one()

    await state.clear()
    
    logger.info(f"Schedule #{schedule_id} type updated to CUSTOM ({message.text}) by {message.from_user.id}")

    await message.answer(
        f"✅ <b>Schedule Updated!</b>\n\n"
        f"📅 <b>Schedule #{sched.id}</b>\n"
        f"<b>Type:</b> Custom\n"
        f"<b>Cron:</b> <code>{sched.cron_expr}</code>\n"
        f"<b>Next Run:</b> <code>{format_12hour(sched.next_run)}</code>",
        reply_markup=get_schedule_actions_keyboard(sched.id, sched.is_active),
        parse_mode="HTML"
    )
