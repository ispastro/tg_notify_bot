# Schedule Module Architecture

## Before Refactoring
```
handlers/
  schedule.py (1,100 lines)
    ├─ FSM States
    ├─ Helper Functions
    ├─ Calendar UI
    ├─ Time Picker UI
    ├─ Creation Flow
    ├─ Management Flow
    ├─ Edit Flow
    └─ Legacy Commands
```

## After Refactoring
```
handlers/
  schedule/
    ├─ __init__.py (30 lines)
    │   └─ Imports & exports all modules
    │
    ├─ states.py (25 lines)
    │   ├─ ScheduleStates
    │   └─ EditScheduleStates
    │
    ├─ helpers.py (85 lines)
    │   ├─ format_12hour() → Ethiopia Time (UTC+3)
    │   ├─ ensure_user_exists() → Admin check
    │   └─ save_schedule() → Database save
    │
    ├─ ui.py (100 lines)
    │   ├─ create_calendar() → Calendar widget
    │   ├─ create_time_picker() → Time picker
    │   └─ Navigation handlers (prev/next/day)
    │
    ├─ create.py (280 lines)
    │   ├─ /schedule command
    │   ├─ Batch selection
    │   ├─ Type selection
    │   ├─ Date & time input
    │   ├─ Message input
    │   └─ Confirmation
    │
    ├─ manage.py (320 lines)
    │   ├─ /list_schedules
    │   ├─ /manage_schedules
    │   ├─ View details
    │   ├─ Toggle pause/resume
    │   ├─ Delete confirmation
    │   └─ Legacy commands
    │
    └─ edit.py (380 lines)
        ├─ Edit message
        ├─ Edit time
        ├─ Edit batches
        ├─ Edit type
        └─ Edit cron
```

## Data Flow

### Schedule Creation Flow
```
User → /schedule
  ↓
create.py → Batch Selection
  ↓
create.py → Type Selection
  ↓
ui.py → Calendar Display
  ↓
create.py → Time Input (12-hour)
  ↓
helpers.py → Convert to UTC (subtract 3 hours)
  ↓
create.py → Message Input
  ↓
create.py → Confirmation
  ↓
helpers.py → save_schedule()
  ↓
Database
```

### Schedule Management Flow
```
User → /manage_schedules
  ↓
manage.py → List Schedules
  ↓
manage.py → View Details
  ↓
helpers.py → format_12hour() (add 3 hours for display)
  ↓
User sees Ethiopia Time (UTC+3)
```

### Schedule Edit Flow
```
User → Edit Button
  ↓
edit.py → Show Edit Menu
  ↓
edit.py → Select Edit Type
  ↓
ui.py → Calendar/Time Picker
  ↓
edit.py → Update Database
  ↓
manage.py → Show Updated Schedule
```

## Module Dependencies

```
main.py
  └─ import handlers.schedule
       └─ handlers/schedule/__init__.py
            ├─ import states
            ├─ import helpers
            ├─ import ui
            ├─ import create
            ├─ import manage
            └─ import edit

create.py depends on:
  - states (FSM states)
  - helpers (ensure_user_exists, format_12hour, save_schedule)
  - ui (create_calendar)
  - keyboard.inline (get_batch_keyboard, get_schedule_type_keyboard)

manage.py depends on:
  - helpers (ensure_user_exists, format_12hour)
  - keyboard.inline (get_schedule_list_keyboard, etc.)

edit.py depends on:
  - states (EditScheduleStates)
  - helpers (ensure_user_exists, format_12hour)
  - ui (create_calendar, create_time_picker)
  - keyboard.inline (get_edit_options_keyboard, etc.)

ui.py depends on:
  - helpers (ensure_user_exists)
  - loader (dp for handler registration)
```

## Handler Registration

All handlers are automatically registered via decorators:
```python
@dp.message(Command("schedule"))  # Registered in create.py
@dp.callback_query(F.data.startswith("batch_"))  # Registered in create.py
@dp.callback_query(F.data.startswith("sched_view_"))  # Registered in manage.py
@dp.callback_query(F.data.startswith("edit_msg_"))  # Registered in edit.py
```

When `import handlers.schedule` runs:
1. `__init__.py` imports all submodules
2. Each submodule's decorators register handlers with `dp`
3. All handlers are ready to receive updates

## Key Design Decisions

1. **Single Responsibility**: Each file handles one aspect
2. **Shared Helpers**: Common functions in `helpers.py`
3. **Shared UI**: Reusable widgets in `ui.py`
4. **State Isolation**: FSM states in dedicated `states.py`
5. **No Circular Dependencies**: Clean import hierarchy
6. **Backward Compatible**: Drop-in replacement for old `schedule.py`

## Performance Impact

- **Import Time**: Slightly slower (7 files vs 1), but negligible
- **Runtime**: Identical (same handlers, same logic)
- **Memory**: Identical (same objects loaded)
- **Maintainability**: Significantly improved ✅
