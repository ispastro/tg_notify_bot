# keyboard/inline.py
from aiogram import types
from db.models import Batch, Schedule
from typing import List, Optional

# ==============================================================================
# BATCH SELECTION KEYBOARDS
# ==============================================================================

def get_batch_keyboard(batches: list[Batch], selected: list[int] | None = None):
    """Keyboard for selecting batches during schedule creation."""
    selected = selected or []
    buttons = []
    for b in batches:
        prefix = "✅" if b.id in selected else "⬜"
        buttons.append([
            types.InlineKeyboardButton(
                text=f"{prefix} {b.name}",
                callback_data=f"batch_{b.id}"
            )
        ])
    buttons.append([
        types.InlineKeyboardButton(text="Next ▶️", callback_data="done_batches")
    ])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


def get_schedule_type_keyboard():
    """Keyboard for selecting schedule type."""
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="📅 Weekly", callback_data="type_weekly")],
        [types.InlineKeyboardButton(text="📆 Monthly", callback_data="type_monthly")],
        [types.InlineKeyboardButton(text="⚙️ Custom (cron)", callback_data="type_custom")],
    ])


# ==============================================================================
# SCHEDULE MANAGEMENT KEYBOARDS
# ==============================================================================

def get_schedule_list_keyboard(
    schedules: List[Schedule], 
    page: int = 0, 
    per_page: int = 5
) -> types.InlineKeyboardMarkup:
    """
    Generate paginated schedule list with action buttons.
    
    Args:
        schedules: List of Schedule objects
        page: Current page (0-indexed)
        per_page: Items per page
    """
    buttons = []
    total_pages = max(1, (len(schedules) + per_page - 1) // per_page)
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, len(schedules))
    
    # Schedule items for current page
    for sched in schedules[start_idx:end_idx]:
        status_emoji = "🟢" if sched.is_active else "⏸️"
        
        # Fixed-width preview (exactly 20 chars)
        preview = sched.message[:20].replace("\n", " ")
        if len(sched.message) > 20:
            preview = preview[:17] + "..."
        else:
            # Pad with spaces to maintain alignment
            preview = preview.ljust(20)
        
        # Format: "🟢 #18: Message preview here..."
        button_text = f"{status_emoji} #{sched.id}: {preview}"
        
        buttons.append([
            types.InlineKeyboardButton(
                text=button_text,
                callback_data=f"sched_view_{sched.id}"
            )
        ])
    
    # Pagination row
    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton(
            text="◀️ Prev", 
            callback_data=f"sched_page_{page - 1}"
        ))
    
    nav_row.append(types.InlineKeyboardButton(
        text=f"📄 {page + 1}/{total_pages}",
        callback_data="ignore"
    ))
    
    if page < total_pages - 1:
        nav_row.append(types.InlineKeyboardButton(
            text="Next ▶️", 
            callback_data=f"sched_page_{page + 1}"
        ))
    
    if nav_row:
        buttons.append(nav_row)
    
    # Create new schedule button
    buttons.append([
        types.InlineKeyboardButton(
            text="➕ Create New Schedule",
            callback_data="sched_create_new"
        )
    ])
    
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


def get_schedule_actions_keyboard(
    schedule_id: int, 
    is_active: bool
) -> types.InlineKeyboardMarkup:
    """
    Action buttons for a single schedule.
    
    Args:
        schedule_id: Schedule ID
        is_active: Whether schedule is currently active
    """
    pause_text = "⏸️ Pause" if is_active else "▶️ Resume"
    
    buttons = [
        # Edit actions row
        [
            types.InlineKeyboardButton(
                text="✏️ Edit",
                callback_data=f"sched_edit_{schedule_id}"
            ),
            types.InlineKeyboardButton(
                text=pause_text,
                callback_data=f"sched_toggle_{schedule_id}"
            ),
        ],
        # Delete row
        [
            types.InlineKeyboardButton(
                text="🗑️ Delete",
                callback_data=f"sched_delete_{schedule_id}"
            ),
        ],
        # Navigation
        [
            types.InlineKeyboardButton(
                text="◀️ Back to List",
                callback_data="sched_back_list"
            ),
        ],
    ]
    
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


def get_edit_options_keyboard(schedule_id: int) -> types.InlineKeyboardMarkup:
    """Edit options menu for a schedule."""
    buttons = [
        [
            types.InlineKeyboardButton(
                text="📝 Edit Message",
                callback_data=f"edit_msg_{schedule_id}"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="🕐 Edit Time",
                callback_data=f"edit_time_{schedule_id}"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="📦 Edit Batches",
                callback_data=f"edit_batches_{schedule_id}"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="📅 Edit Type",
                callback_data=f"edit_type_{schedule_id}"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="◀️ Back",
                callback_data=f"sched_view_{schedule_id}"
            ),
        ],
    ]
    
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


def get_confirm_delete_keyboard(schedule_id: int) -> types.InlineKeyboardMarkup:
    """Confirmation dialog for deleting a schedule."""
    buttons = [
        [
            types.InlineKeyboardButton(
                text="✅ Yes, Delete Permanently",
                callback_data=f"sched_confirm_del_{schedule_id}"
            ),
        ],
        [
            types.InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=f"sched_view_{schedule_id}"
            ),
        ],
    ]
    
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


def get_edit_batch_keyboard(
    batches: list[Batch], 
    selected: list[int],
    schedule_id: int
) -> types.InlineKeyboardMarkup:
    """Keyboard for editing batches of an existing schedule."""
    buttons = []
    for b in batches:
        prefix = "✅" if b.id in selected else "⬜"
        buttons.append([
            types.InlineKeyboardButton(
                text=f"{prefix} {b.name}",
                callback_data=f"edit_batch_sel_{schedule_id}_{b.id}"
            )
        ])
    buttons.append([
        types.InlineKeyboardButton(
            text="💾 Save Changes", 
            callback_data=f"edit_batch_save_{schedule_id}"
        ),
        types.InlineKeyboardButton(
            text="❌ Cancel", 
            callback_data=f"sched_view_{schedule_id}"
        ),
    ])
    return types.InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cancel_keyboard(schedule_id: int) -> types.InlineKeyboardMarkup:
    """Simple cancel button to go back to schedule view."""
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(
            text="❌ Cancel",
            callback_data=f"sched_view_{schedule_id}"
        )]
    ])