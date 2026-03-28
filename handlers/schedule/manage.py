# handlers/schedule/manage.py
"""Schedule management (list, view, toggle, delete)."""
from aiogram import types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from loader import dp
from db.session import AsyncSessionLocal
from db.models import Schedule, Batch, schedule_batch_association
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from keyboard.inline import (
    get_schedule_list_keyboard,
    get_schedule_actions_keyboard,
    get_confirm_delete_keyboard,
)
from .helpers import ensure_user_exists, format_12hour
import logging

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# /list_schedules COMMAND
# ----------------------------------------------------------------------
@dp.message(Command("list_schedules"))
async def cmd_list_schedules(message: types.Message):
    """List all schedules with details."""
    if not await ensure_user_exists(message.from_user.id):
        await message.answer("No permission.")
        return

    async with AsyncSessionLocal() as session:
        schedules = (await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).order_by(Schedule.id.desc())
        )).scalars().all()

    if not schedules:
        await message.answer(
            "📭 <b>No Schedules Found</b>\n\n"
            "Use /schedule to create your first broadcast.",
            parse_mode="HTML"
        )
        return

    # Header with stats
    active_count = sum(1 for s in schedules if s.is_active)
    paused_count = len(schedules) - active_count
    
    header = (
        f"📋 <b>All Schedules ({len(schedules)})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✅ Active: <code>{active_count}</code> | "
        f"⏸️ Paused: <code>{paused_count}</code>\n\n"
    )

    lines = []
    for s in schedules:
        status = "✅" if s.is_active else "⏸️"
        batches = ", ".join(b.name for b in s.batches) if s.batches else "None"
        msg_preview = s.message[:40].replace("\n", " ")
        if len(s.message) > 40:
            msg_preview += "..."
        
        lines.append(
            f"<b>#{s.id}</b> {status} | {s.type.value.title()}\n"
            f"  ⏰ {format_12hour(s.next_run)}\n"
            f"  📦 {batches}\n"
            f"  💬 <i>{msg_preview}</i>"
        )

    await message.answer(
        header + "\n━━━━━━━━━━━━━━━━━━━━━━\n\n".join(lines),
        parse_mode="HTML"
    )


# ----------------------------------------------------------------------
# /manage_schedules COMMAND
# ----------------------------------------------------------------------
@dp.message(Command("manage_schedules"))
async def cmd_manage_schedules(message: types.Message, state: FSMContext):
    """Display interactive schedule management panel."""
    if not await ensure_user_exists(message.from_user.id, message.from_user.username):
        await message.answer("❌ You don't have permission to manage schedules.")
        return

    await state.clear()
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).order_by(Schedule.id.desc())
        )
        schedules = result.scalars().all()

    if not schedules:
        await message.answer(
            "📭 <b>No Schedules Found</b>\n\n"
            "Use /schedule to create your first scheduled broadcast.",
            parse_mode="HTML"
        )
        return

    active_count = sum(1 for s in schedules if s.is_active)
    paused_count = len(schedules) - active_count

    await message.answer(
        f"📋 <b>Schedule Management</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Statistics:</b>\n"
        f"• Total: <code>{len(schedules)}</code>\n"
        f"• Active: <code>{active_count}</code> ✅\n"
        f"• Paused: <code>{paused_count}</code> ⏸️\n\n"
        f"👇 Select a schedule to manage:",
        reply_markup=get_schedule_list_keyboard(schedules, page=0),
        parse_mode="HTML"
    )


# ----------------------------------------------------------------------
# PAGINATION HANDLER
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("sched_page_"))
async def handle_schedule_pagination(callback: types.CallbackQuery, state: FSMContext):
    """Handle pagination in schedule list."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    page = int(callback.data.split("_")[2])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).order_by(Schedule.id.desc())
        )
        schedules = result.scalars().all()

    await callback.message.edit_reply_markup(
        reply_markup=get_schedule_list_keyboard(schedules, page=page)
    )
    await callback.answer()


# ----------------------------------------------------------------------
# VIEW SCHEDULE DETAILS
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("sched_view_"))
async def handle_view_schedule(callback: types.CallbackQuery, state: FSMContext):
    """Display detailed view of a single schedule."""
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

    status = "🟢 Active" if sched.is_active else "⏸️ Paused"
    batches = ", ".join(b.name for b in sched.batches) if sched.batches else "None"
    next_run_str = format_12hour(sched.next_run) if sched.next_run else "Not scheduled"
    cron_info = f"\n🔄 <b>Cron:</b> <code>{sched.cron_expr}</code>" if sched.cron_expr else ""
    
    # Truncate message preview
    msg_preview = sched.message[:200] + "..." if len(sched.message) > 200 else sched.message

    text = (
        f"📅 <b>Schedule #{sched.id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Status:</b> {status}\n"
        f"📋 <b>Type:</b> {sched.type.value.title()}\n"
        f"📦 <b>Batches:</b> {batches}\n"
        f"⏰ <b>Next Run:</b>\n<code>{next_run_str}</code>{cron_info}\n"
        f"📆 <b>Created:</b> {sched.created_at.strftime('%b %d, %Y') if sched.created_at else 'Unknown'}\n\n"
        f"💬 <b>Message Preview:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>{msg_preview}</blockquote>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_schedule_actions_keyboard(sched.id, sched.is_active),
        parse_mode="HTML"
    )
    await callback.answer()


# ----------------------------------------------------------------------
# BACK TO SCHEDULE LIST
# ----------------------------------------------------------------------
@dp.callback_query(F.data == "sched_back_list")
async def handle_back_to_list(callback: types.CallbackQuery, state: FSMContext):
    """Go back to schedule list."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    await state.clear()
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).order_by(Schedule.id.desc())
        )
        schedules = result.scalars().all()

    if not schedules:
        await callback.message.edit_text(
            "📭 <b>No Schedules Found</b>\n\n"
            "Use /schedule to create a new broadcast.",
            parse_mode="HTML"
        )
        return

    active_count = sum(1 for s in schedules if s.is_active)
    paused_count = len(schedules) - active_count

    await callback.message.edit_text(
        f"📋 <b>Schedule Management</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Statistics:</b>\n"
        f"• Total: <code>{len(schedules)}</code>\n"
        f"• Active: <code>{active_count}</code> ✅\n"
        f"• Paused: <code>{paused_count}</code> ⏸️\n\n"
        f"👇 Select a schedule to manage:",
        reply_markup=get_schedule_list_keyboard(schedules, page=0),
        parse_mode="HTML"
    )
    await callback.answer()


# ----------------------------------------------------------------------
# CREATE NEW SCHEDULE (from management panel)
# ----------------------------------------------------------------------
@dp.callback_query(F.data == "sched_create_new")
async def handle_create_new_schedule(callback: types.CallbackQuery, state: FSMContext):
    """Start new schedule creation flow."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        batches = (await session.execute(select(Batch))).scalars().all()

    if not batches:
        await callback.answer("No batches found!", show_alert=True)
        return

    from keyboard.inline import get_batch_keyboard
    from .states import ScheduleStates
    
    await callback.message.edit_text(
        "➕ <b>Create New Schedule</b>\n\nSelect target batches:",
        reply_markup=get_batch_keyboard(batches),
        parse_mode="HTML"
    )
    await state.set_state(ScheduleStates.choosing_batches)
    await callback.answer()


# ----------------------------------------------------------------------
# TOGGLE PAUSE/RESUME
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("sched_toggle_"))
async def handle_toggle_schedule(callback: types.CallbackQuery, state: FSMContext):
    """Toggle schedule active/paused status."""
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
        
        new_status = not sched.is_active
        await session.execute(
            update(Schedule).where(Schedule.id == schedule_id).values(is_active=new_status)
        )
        await session.commit()
        
        # Refresh schedule object
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).where(Schedule.id == schedule_id)
        )
        sched = result.scalar_one()

    action = "resumed ▶️" if new_status else "paused ⏸️"
    await callback.answer(f"Schedule #{schedule_id} {action}", show_alert=True)
    
    # Refresh the view
    status = "🟢 Active" if sched.is_active else "⏸️ Paused"
    batches = ", ".join(b.name for b in sched.batches) if sched.batches else "None"
    next_run_str = format_12hour(sched.next_run) if sched.next_run else "Not scheduled"
    cron_info = f"\n🔄 <b>Cron:</b> <code>{sched.cron_expr}</code>" if sched.cron_expr else ""
    msg_preview = sched.message[:200] + "..." if len(sched.message) > 200 else sched.message

    text = (
        f"📅 <b>Schedule #{sched.id}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Status:</b> {status}\n"
        f"📋 <b>Type:</b> {sched.type.value.title()}\n"
        f"📦 <b>Batches:</b> {batches}\n"
        f"⏰ <b>Next Run:</b>\n<code>{next_run_str}</code>{cron_info}\n"
        f"📆 <b>Created:</b> {sched.created_at.strftime('%b %d, %Y') if sched.created_at else 'Unknown'}\n\n"
        f"💬 <b>Message Preview:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<blockquote>{msg_preview}</blockquote>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_schedule_actions_keyboard(sched.id, sched.is_active),
        parse_mode="HTML"
    )


# ----------------------------------------------------------------------
# DELETE CONFIRMATION
# ----------------------------------------------------------------------
@dp.callback_query(F.data.startswith("sched_delete_"))
async def handle_delete_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """Show delete confirmation dialog."""
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
        f"⚠️ <b>Delete Schedule #{schedule_id}?</b>\n\n"
        f"<b>This action cannot be undone!</b>\n\n"
        f"The schedule will be permanently deleted along with all its settings.",
        reply_markup=get_confirm_delete_keyboard(schedule_id),
        parse_mode="HTML"
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("sched_confirm_del_"))
async def handle_confirm_delete(callback: types.CallbackQuery, state: FSMContext):
    """Permanently delete a schedule."""
    if not await ensure_user_exists(callback.from_user.id):
        await callback.answer("No permission.", show_alert=True)
        return

    schedule_id = int(callback.data.split("_")[3])
    
    async with AsyncSessionLocal() as session:
        # Delete associations first
        await session.execute(
            delete(schedule_batch_association).where(
                schedule_batch_association.c.schedule_id == schedule_id
            )
        )
        # Delete schedule
        await session.execute(delete(Schedule).where(Schedule.id == schedule_id))
        await session.commit()

    logger.info(f"Schedule #{schedule_id} DELETED by admin {callback.from_user.id}")

    await callback.answer(f"Schedule #{schedule_id} deleted!", show_alert=True)
    
    # Go back to list
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Schedule).options(selectinload(Schedule.batches)).order_by(Schedule.id.desc())
        )
        schedules = result.scalars().all()

    if not schedules:
        await callback.message.edit_text(
            "📭 <b>No Schedules Remaining</b>\n\n"
            "Use /schedule to create a new scheduled broadcast.",
            parse_mode="HTML"
        )
        return

    active_count = sum(1 for s in schedules if s.is_active)
    paused_count = len(schedules) - active_count

    await callback.message.edit_text(
        f"📋 <b>Schedule Management</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Statistics:</b>\n"
        f"• Total: <code>{len(schedules)}</code>\n"
        f"• Active: <code>{active_count}</code> ✅\n"
        f"• Paused: <code>{paused_count}</code> ⏸️\n\n"
        f"👇 Select a schedule to manage:",
        reply_markup=get_schedule_list_keyboard(schedules, page=0),
        parse_mode="HTML"
    )


# ----------------------------------------------------------------------
# LEGACY COMMAND HANDLERS (backward compatibility)
# ----------------------------------------------------------------------
@dp.message(Command("pause_schedule"))
async def cmd_pause_schedule(message: types.Message):
    """Pause a schedule by ID (legacy command)."""
    if not await ensure_user_exists(message.from_user.id): 
        return await message.answer("No permission.")
    try:
        sched_id = int(message.text.split(maxsplit=1)[1])
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Schedule).where(Schedule.id == sched_id))
            sched = result.scalar_one_or_none()
            if not sched:
                await message.answer(f"Schedule #{sched_id} not found.")
                return
            await session.execute(update(Schedule).where(Schedule.id == sched_id).values(is_active=False))
            await session.commit()
        logger.info(f"Schedule #{sched_id} paused by admin {message.from_user.id}")
        await message.answer(f"⏸️ Schedule <b>#{sched_id}</b> paused.", parse_mode="HTML")
    except (IndexError, ValueError):
        await message.answer("Usage: <code>/pause_schedule &lt;id&gt;</code>", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error pausing schedule: {e}")
        await message.answer("An error occurred.")


@dp.message(Command("resume_schedule"))
async def cmd_resume_schedule(message: types.Message):
    """Resume a schedule by ID (legacy command)."""
    if not await ensure_user_exists(message.from_user.id): 
        return await message.answer("No permission.")
    try:
        sched_id = int(message.text.split(maxsplit=1)[1])
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Schedule).where(Schedule.id == sched_id))
            sched = result.scalar_one_or_none()
            if not sched:
                await message.answer(f"Schedule #{sched_id} not found.")
                return
            await session.execute(update(Schedule).where(Schedule.id == sched_id).values(is_active=True))
            await session.commit()
        logger.info(f"Schedule #{sched_id} resumed by admin {message.from_user.id}")
        await message.answer(f"▶️ Schedule <b>#{sched_id}</b> resumed.", parse_mode="HTML")
    except (IndexError, ValueError):
        await message.answer("Usage: <code>/resume_schedule &lt;id&gt;</code>", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error resuming schedule: {e}")
        await message.answer("An error occurred.")


@dp.message(Command("delete_schedule"))
async def cmd_delete_schedule(message: types.Message):
    """Delete a schedule by ID (legacy command)."""
    if not await ensure_user_exists(message.from_user.id): 
        return await message.answer("No permission.")
    try:
        sched_id = int(message.text.split(maxsplit=1)[1])
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Schedule).where(Schedule.id == sched_id))
            sched = result.scalar_one_or_none()
            if not sched:
                await message.answer(f"Schedule #{sched_id} not found.")
                return
            await session.execute(
                delete(schedule_batch_association).where(
                    schedule_batch_association.c.schedule_id == sched_id
                )
            )
            await session.execute(delete(Schedule).where(Schedule.id == sched_id))
            await session.commit()
        logger.info(f"Schedule #{sched_id} DELETED by admin {message.from_user.id}")
        await message.answer(f"🗑️ Schedule <b>#{sched_id}</b> deleted permanently.", parse_mode="HTML")
    except (IndexError, ValueError):
        await message.answer("Usage: <code>/delete_schedule &lt;id&gt;</code>", parse_mode="HTML")
    except Exception as e:
        logger.error(f"Error deleting schedule: {e}")
        await message.answer("An error occurred.")
