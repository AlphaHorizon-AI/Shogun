import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from '../lib/routerCompat';
import { 
  Calendar, ChevronLeft, ChevronRight, Plus, Trash2, Edit3, 
  Clock, MapPin, X, RefreshCw, ShieldAlert, AlertCircle, Settings
} from 'lucide-react';
import { cn } from '../lib/utils';

// Types
interface EmailAccount {
  id: string;
  provider: string;
  email_address: string;
  display_name?: string;
  is_active: boolean;
  calendar_provider: string;
  perm_read_calendar: boolean;
  perm_create_events: boolean;
  perm_edit_events: boolean;
  perm_delete_events: boolean;
}

interface CalendarEvent {
  id: string;
  title: string;
  start: string; // ISO datetime string
  end: string;   // ISO datetime string
  location?: string | null;
  description?: string | null;
  all_day?: boolean;
  color?: string | null;
}

export const CalendarView = () => {
  const navigate = useNavigate();
  const [account, setAccount] = useState<EmailAccount | null>(null);
  const [loadingAccount, setLoadingAccount] = useState(true);
  
  // Date and View states
  const [currentDate, setCurrentDate] = useState<Date>(new Date());
  const [viewMode, setViewMode] = useState<'month' | 'week' | 'day'>('month');
  
  // Events state
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  
  // Modals state
  const [showEventModal, setShowEventModal] = useState(false);
  const [modalMode, setModalMode] = useState<'create' | 'view' | 'edit'>('create');
  const [selectedEvent, setSelectedEvent] = useState<CalendarEvent | null>(null);
  
  // Form states
  const [eventTitle, setEventTitle] = useState('');
  const [eventStart, setEventStart] = useState('');
  const [eventEnd, setEventEnd] = useState('');
  const [eventLocation, setEventLocation] = useState('');
  const [eventDescription, setEventDescription] = useState('');
  const [eventAllDay, setEventAllDay] = useState(false);
  const [submittingEvent, setSubmittingEvent] = useState(false);
  const [formError, setFormError] = useState('');

  // Fetch account status
  const fetchAccount = async () => {
    try {
      const res = await axios.get('/api/v1/channels/email/account');
      setAccount(res.data.data);
    } catch {
      setAccount(null);
    } finally {
      setLoadingAccount(false);
    }
  };

  useEffect(() => {
    fetchAccount();
  }, []);

  // Calculate start and end range for the current view
  const getViewRange = () => {
    const start = new Date(currentDate);
    const end = new Date(currentDate);

    if (viewMode === 'month') {
      // Start of month grid (usually includes some prev month days)
      start.setDate(1);
      const firstDayOffset = start.getDay();
      start.setDate(start.getDate() - firstDayOffset);
      start.setHours(0, 0, 0, 0);

      // End of month grid
      end.setMonth(end.getMonth() + 1);
      end.setDate(0); // Last day of current month
      const lastDayOffset = 6 - end.getDay();
      end.setDate(end.getDate() + lastDayOffset);
      end.setHours(23, 59, 59, 999);
    } else if (viewMode === 'week') {
      // Start of week (Sunday)
      const day = start.getDay();
      start.setDate(start.getDate() - day);
      start.setHours(0, 0, 0, 0);

      // End of week (Saturday)
      end.setDate(start.getDate() + 6);
      end.setHours(23, 59, 59, 999);
    } else {
      // Day view (single day)
      start.setHours(0, 0, 0, 0);
      end.setHours(23, 59, 59, 999);
    }

    return { start, end };
  };

  // Fetch CalDAV events
  const fetchEvents = async () => {
    if (!account?.is_active || !account.perm_read_calendar || account.calendar_provider === 'none') {
      return;
    }
    setLoadingEvents(true);
    setErrorMsg('');
    const { start, end } = getViewRange();
    
    try {
      const res = await axios.get('/api/v1/channels/calendar/events', {
        params: {
          start: start.toISOString(),
          end: end.toISOString()
        }
      });
      setEvents(res.data.data || []);
    } catch (err: any) {
      console.error("Failed to fetch events", err);
      setErrorMsg(err.response?.data?.detail || 'Failed to sync calendar events.');
    } finally {
      setLoadingEvents(false);
    }
  };

  useEffect(() => {
    if (account?.is_active && account.perm_read_calendar) {
      fetchEvents();
    }
  }, [account, currentDate, viewMode]);

  // Navigate view range
  const handlePrev = () => {
    const nextDate = new Date(currentDate);
    if (viewMode === 'month') {
      nextDate.setMonth(nextDate.getMonth() - 1);
    } else if (viewMode === 'week') {
      nextDate.setDate(nextDate.getDate() - 7);
    } else {
      nextDate.setDate(nextDate.getDate() - 1);
    }
    setCurrentDate(nextDate);
  };

  const handleNext = () => {
    const nextDate = new Date(currentDate);
    if (viewMode === 'month') {
      nextDate.setMonth(nextDate.getMonth() + 1);
    } else if (viewMode === 'week') {
      nextDate.setDate(nextDate.getDate() + 7);
    } else {
      nextDate.setDate(nextDate.getDate() + 1);
    }
    setCurrentDate(nextDate);
  };

  const handleToday = () => {
    setCurrentDate(new Date());
  };

  // Format Helper to convert local Date objects into datetime-local input string (YYYY-MM-DDTHH:MM)
  const formatDatetimeLocal = (date: Date) => {
    const tzOffset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - tzOffset).toISOString().slice(0, 16);
  };

  // Event CRUD Handlers
  const openCreateModal = (initialDate?: Date) => {
    if (!account?.perm_create_events) return;
    setFormError('');
    setModalMode('create');
    setEventTitle('');
    setEventLocation('');
    setEventDescription('');
    setEventAllDay(false);

    const start = initialDate ? new Date(initialDate) : new Date();
    if (!initialDate) {
      start.setMinutes(0, 0, 0);
      start.setHours(start.getHours() + 1);
    } else {
      start.setHours(9, 0, 0, 0);
    }
    
    const end = new Date(start);
    end.setHours(end.getHours() + 1);

    setEventStart(formatDatetimeLocal(start));
    setEventEnd(formatDatetimeLocal(end));
    setShowEventModal(true);
  };

  const openViewModal = (event: CalendarEvent) => {
    setSelectedEvent(event);
    setModalMode('view');
    setEventTitle(event.title);
    setEventStart(formatDatetimeLocal(new Date(event.start)));
    setEventEnd(formatDatetimeLocal(new Date(event.end)));
    setEventLocation(event.location || '');
    setEventDescription(event.description || '');
    setEventAllDay(event.all_day || false);
    setFormError('');
    setShowEventModal(true);
  };

  const switchEditMode = () => {
    if (!account?.perm_edit_events) return;
    setModalMode('edit');
  };

  const handleCreateOrUpdateEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');
    
    const startObj = new Date(eventStart);
    const endObj = new Date(eventEnd);

    if (endObj <= startObj) {
      setFormError('End date/time must be after the start date/time.');
      return;
    }

    setSubmittingEvent(true);
    try {
      const payload = {
        title: eventTitle,
        start: startObj.toISOString(),
        end: endObj.toISOString(),
        location: eventLocation || null,
        description: eventDescription || null,
        all_day: eventAllDay
      };

      if (modalMode === 'create') {
        await axios.post('/api/v1/channels/calendar/events', payload);
      } else if (modalMode === 'edit' && selectedEvent) {
        await axios.patch(`/api/v1/channels/calendar/events/${selectedEvent.id}`, payload);
      }

      setShowEventModal(false);
      fetchEvents();
    } catch (err: any) {
      console.error("Failed to save event", err);
      setFormError(err.response?.data?.detail || 'Failed to save calendar event.');
    } finally {
      setSubmittingEvent(false);
    }
  };

  const handleDeleteEvent = async () => {
    if (!selectedEvent || !account?.perm_delete_events) return;
    if (!window.confirm('Are you sure you want to delete this event?')) return;

    setSubmittingEvent(true);
    setFormError('');
    try {
      await axios.delete(`/api/v1/channels/calendar/events/${selectedEvent.id}`);
      setShowEventModal(false);
      fetchEvents();
    } catch (err: any) {
      console.error("Failed to delete event", err);
      setFormError(err.response?.data?.detail || 'Failed to delete event.');
    } finally {
      setSubmittingEvent(false);
    }
  };

  // Calendar Grid / Render Helpers
  const getDaysInMonth = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();
    const firstDayIndex = new Date(year, month, 1).getDay(); // 0 is Sunday
    const totalDays = new Date(year, month + 1, 0).getDate();
    const prevMonthTotalDays = new Date(year, month, 0).getDate();
    
    const days = [];
    // Prev month padding days
    for (let i = firstDayIndex - 1; i >= 0; i--) {
      const d = new Date(year, month - 1, prevMonthTotalDays - i);
      days.push({
        date: d,
        isCurrentMonth: false,
        key: `prev-${i}`
      });
    }
    // Current month days
    for (let i = 1; i <= totalDays; i++) {
      const d = new Date(year, month, i);
      days.push({
        date: d,
        isCurrentMonth: true,
        key: `curr-${i}`
      });
    }
    // Next month padding days (complete grid to 42 cells)
    const remaining = 42 - days.length;
    for (let i = 1; i <= remaining; i++) {
      const d = new Date(year, month + 1, i);
      days.push({
        date: d,
        isCurrentMonth: false,
        key: `next-${i}`
      });
    }
    return days;
  };

  const getWeekDays = () => {
    const start = new Date(currentDate);
    const day = start.getDay();
    start.setDate(start.getDate() - day);
    
    const days = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(start);
      d.setDate(start.getDate() + i);
      days.push(d);
    }
    return days;
  };

  // Check if dates are the same calendar day
  const isSameDay = (d1: Date, d2: Date) => {
    return d1.getFullYear() === d2.getFullYear() &&
           d1.getMonth() === d2.getMonth() &&
           d1.getDate() === d2.getDate();
  };

  // Filter events matching a day
  const getEventsForDay = (day: Date) => {
    return events.filter(event => {
      const eventStart = new Date(event.start);
      return isSameDay(eventStart, day);
    }).sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
  };

  // Header Title generation
  const getTitle = () => {
    if (viewMode === 'month') {
      return currentDate.toLocaleString('default', { month: 'long', year: 'numeric' });
    } else if (viewMode === 'week') {
      const days = getWeekDays();
      const start = days[0];
      const end = days[6];
      if (start.getMonth() === end.getMonth()) {
        return `${start.toLocaleString('default', { month: 'long' })} ${start.getFullYear()}`;
      } else if (start.getFullYear() === end.getFullYear()) {
        return `${start.toLocaleString('default', { month: 'short' })} – ${end.toLocaleString('default', { month: 'short' })} ${start.getFullYear()}`;
      } else {
        return `${start.toLocaleString('default', { month: 'short', year: 'numeric' })} – ${end.toLocaleString('default', { month: 'short', year: 'numeric' })}`;
      }
    } else {
      return currentDate.toLocaleDateString('default', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' });
    }
  };

  // Common UI logic for loading/error/none states
  if (loadingAccount) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-shogun-subdued space-y-4">
        <RefreshCw className="w-8 h-8 animate-spin text-shogun-blue" />
        <p className="text-xs uppercase tracking-widest font-bold">Synchronizing Calendar Board…</p>
      </div>
    );
  }

  if (!account || !account.is_active || account.calendar_provider === 'none') {
    return (
      <div className="h-full flex flex-col items-center justify-center text-shogun-subdued text-center p-8">
        <div className="w-16 h-16 rounded-full bg-shogun-blue/10 flex items-center justify-center text-shogun-blue border border-shogun-blue/30 mb-4 animate-pulse">
          <Calendar className="w-8 h-8" />
        </div>
        <h4 className="text-lg font-bold text-shogun-text mb-2">No Calendar Account Connected</h4>
        <p className="max-w-md text-xs text-shogun-subdued leading-relaxed mb-6">
          To manage schedules and CalDAV events, configure your Calendar provider in Katana settings.
        </p>
        <button
          onClick={() => { navigate('/katana'); }}
          className="px-5 py-2.5 bg-shogun-blue hover:bg-shogun-blue/90 text-white text-xs font-bold rounded-lg uppercase tracking-wider transition-all"
        >
          Go to Katana Settings
        </button>
      </div>
    );
  }

  if (!account.perm_read_calendar) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-shogun-subdued text-center p-8">
        <div className="w-16 h-16 rounded-full bg-red-400/10 flex items-center justify-center text-red-400 border border-red-400/30 mb-4">
          <ShieldAlert className="w-8 h-8" />
        </div>
        <h4 className="text-lg font-bold text-shogun-text mb-2">Read Permission Denied</h4>
        <p className="max-w-md text-xs text-shogun-subdued leading-relaxed">
          The "Read Calendar" permission is disabled for this account in Katana settings. Toggle this permission ON to view your calendar board.
        </p>
      </div>
    );
  }

  const weekdaysHeader = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  return (
    <div className="h-[calc(100vh-270px)] flex flex-col min-h-0 bg-[#050508]/30 rounded-2xl border border-shogun-border/40 overflow-hidden backdrop-blur-md">
      {/* Top action bar */}
      <div className="flex flex-col sm:flex-row justify-between items-stretch sm:items-center px-6 py-4 bg-[#0a0a0f]/60 border-b border-shogun-border/40 gap-3 shrink-0">
        {/* Navigation & Title */}
        <div className="flex items-center gap-4">
          <div className="flex items-center border border-shogun-border rounded-lg bg-shogun-card overflow-hidden">
            <button
              onClick={handlePrev}
              className="p-2 text-shogun-subdued hover:text-shogun-text hover:bg-white/5 transition-all"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={handleToday}
              className="px-3 py-1.5 text-xs font-bold uppercase border-x border-shogun-border text-shogun-subdued hover:text-shogun-text hover:bg-white/5 transition-all"
            >
              Today
            </button>
            <button
              onClick={handleNext}
              className="p-2 text-shogun-subdued hover:text-shogun-text hover:bg-white/5 transition-all"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <h3 className="text-sm font-bold text-shogun-text font-mono truncate">{getTitle()}</h3>
        </div>

        {/* View Toggles & Add Event */}
        <div className="flex items-center gap-2.5">
          {errorMsg && (
            <div className="hidden lg:flex items-center gap-1.5 px-3 py-1 bg-red-500/10 border border-red-500/20 text-red-400 rounded-md text-[10px] font-bold">
              <AlertCircle className="w-3.5 h-3.5" />
              <span>Sync Error</span>
            </div>
          )}

          <button
            onClick={fetchEvents}
            className="p-2 border border-shogun-border bg-shogun-card hover:bg-shogun-card/80 text-shogun-subdued hover:text-shogun-text rounded-lg transition-all"
            title="Refresh events"
          >
            <RefreshCw className={cn("w-4 h-4", loadingEvents && "animate-spin")} />
          </button>

          <div className="flex border border-shogun-border rounded-lg bg-shogun-card p-0.5">
            {(['month', 'week', 'day'] as const).map(mode => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={cn(
                  "px-3 py-1 rounded-md text-xs font-bold uppercase tracking-wider transition-all",
                  viewMode === mode 
                    ? "bg-shogun-blue/10 text-shogun-blue border border-shogun-blue/20" 
                    : "text-shogun-subdued hover:text-shogun-text"
                )}
              >
                {mode}
              </button>
            ))}
          </div>

          <button
            onClick={() => navigate('/shogun?tab=operations')}
            className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold rounded-lg text-xs uppercase tracking-wider transition-all border border-purple-500/20 shadow-[0_0_10px_rgba(147,51,234,0.3)] hover:shadow-[0_0_15px_rgba(147,51,234,0.5)]"
          >
            <Plus className="w-4 h-4" /> Create Task
          </button>

          {account.perm_create_events && (
            <button
              onClick={() => openCreateModal()}
              className="flex items-center gap-1.5 px-4 py-2 bg-shogun-blue hover:bg-shogun-blue/90 text-white font-bold rounded-lg text-xs uppercase tracking-wider transition-all"
            >
              <Plus className="w-4 h-4" /> Add Event
            </button>
          )}
        </div>
      </div>

      {/* Main Grid View Area */}
      <div className="flex-1 overflow-hidden relative flex flex-col bg-[#07070a]/20">
        {loadingEvents && (
          <div className="absolute inset-0 bg-[#050508]/60 backdrop-blur-[2px] z-20 flex flex-col items-center justify-center text-shogun-subdued space-y-2">
            <RefreshCw className="w-6 h-6 animate-spin text-shogun-blue" />
            <span className="text-[10px] uppercase tracking-widest font-bold">Querying CalDAV Node…</span>
          </div>
        )}

        {/* ── MONTH VIEW ── */}
        {viewMode === 'month' && (
          <div className="flex-1 flex flex-col min-h-0">
            {/* Weekday headers */}
            <div className="grid grid-cols-7 border-b border-shogun-border/30 bg-[#0a0a0f]/40 text-center py-2 shrink-0">
              {weekdaysHeader.map(day => (
                <span key={day} className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{day}</span>
              ))}
            </div>

            {/* Calendar days grid */}
            <div className="flex-1 grid grid-cols-7 grid-rows-6 divide-x divide-y divide-shogun-border/20 min-h-0 overflow-y-auto">
              {getDaysInMonth().map(({ date, isCurrentMonth, key }) => {
                const dayEvents = getEventsForDay(date);
                const isToday = isSameDay(date, new Date());
                
                return (
                  <div
                    key={key}
                    onClick={() => {
                      if (account.perm_create_events) {
                        openCreateModal(date);
                      } else {
                        setViewMode('day');
                        setCurrentDate(date);
                      }
                    }}
                    className={cn(
                      "min-h-0 p-2 flex flex-col gap-1 transition-all cursor-pointer select-none relative group",
                      isCurrentMonth ? "bg-transparent" : "bg-[#07070a]/10 opacity-40",
                      isToday ? "bg-shogun-blue/[0.02]" : "hover:bg-shogun-card/15"
                    )}
                  >
                    {/* Day number */}
                    <div className="flex justify-between items-center shrink-0">
                      <span className={cn(
                        "text-xs font-mono font-bold w-6 h-6 flex items-center justify-center rounded-full transition-all",
                        isToday ? "bg-shogun-blue text-white shadow-[0_0_10px_rgba(74,140,199,0.5)]" : "text-shogun-text group-hover:text-shogun-blue"
                      )}>
                        {date.getDate()}
                      </span>
                      {dayEvents.length > 0 && (
                        <span className="text-[9px] font-bold text-shogun-subdued bg-shogun-card border border-shogun-border/40 px-1.5 py-0.5 rounded font-mono">
                          {dayEvents.length}
                        </span>
                      )}
                    </div>

                    {/* Events preview list inside day box */}
                    <div className="flex-1 flex flex-col gap-1 overflow-y-auto scrollbar-hide py-1">
                      {dayEvents.slice(0, 3).map(event => (
                        <div
                          key={event.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            openViewModal(event);
                          }}
                          className={cn(
                            "px-2 py-1 rounded text-[10px] font-medium truncate border transition-all text-left",
                            event.color === 'cron_job'
                              ? "bg-gradient-to-r from-purple-950/40 to-indigo-950/40 border-purple-500/30 text-purple-200 hover:from-purple-900/50 hover:to-indigo-900/50 shadow-[0_0_8px_rgba(168,85,247,0.15)]"
                              : event.all_day 
                                ? "bg-shogun-gold/15 border-shogun-gold/30 text-shogun-gold hover:bg-shogun-gold/25"
                                : "bg-shogun-blue/15 border-shogun-blue/30 text-shogun-blue hover:bg-shogun-blue/25"
                          )}
                          title={`${event.title} (${new Date(event.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})`}
                        >
                          {!event.all_day && (
                            <span className="font-mono opacity-85 mr-1 font-bold">
                              {new Date(event.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}
                            </span>
                          )}
                          {event.title}
                        </div>
                      ))}
                      {dayEvents.length > 3 && (
                        <div className="text-[9px] font-bold text-shogun-subdued italic px-1">
                          + {dayEvents.length - 3} more
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── WEEK VIEW ── */}
        {viewMode === 'week' && (
          <div className="flex-1 flex divide-x divide-shogun-border/20 min-h-0 overflow-x-auto">
            {getWeekDays().map((day, idx) => {
              const dayEvents = getEventsForDay(day);
              const isToday = isSameDay(day, new Date());

              return (
                <div
                  key={idx}
                  className={cn(
                    "flex-1 min-w-[140px] flex flex-col min-h-0 bg-[#07070a]/10",
                    isToday && "bg-shogun-blue/[0.01] border-x border-shogun-blue/10"
                  )}
                >
                  {/* Column header */}
                  <div className={cn(
                    "p-3 border-b border-shogun-border/30 bg-[#0a0a0f]/40 text-center shrink-0 flex flex-col items-center justify-center gap-0.5",
                    isToday && "border-b-shogun-blue/50"
                  )}>
                    <span className="text-[10px] font-bold text-shogun-subdued uppercase tracking-wider">
                      {day.toLocaleDateString('default', { weekday: 'short' })}
                    </span>
                    <span className={cn(
                      "text-sm font-mono font-bold w-7 h-7 flex items-center justify-center rounded-full",
                      isToday ? "bg-shogun-blue text-white shadow-[0_0_8px_rgba(74,140,199,0.5)]" : "text-shogun-text"
                    )}>
                      {day.getDate()}
                    </span>
                  </div>

                  {/* Column content */}
                  <div 
                    onClick={() => { if (account.perm_create_events) openCreateModal(day); }}
                    className="flex-1 p-3 overflow-y-auto space-y-2.5 cursor-pointer hover:bg-shogun-card/[0.03] transition-colors"
                  >
                    {dayEvents.length === 0 ? (
                      <div className="h-full flex items-center justify-center">
                        <span className="text-[9px] text-shogun-subdued font-bold tracking-wider uppercase opacity-35">No Events</span>
                      </div>
                    ) : (
                      dayEvents.map(event => (
                        <div
                          key={event.id}
                          onClick={(e) => {
                            e.stopPropagation();
                            openViewModal(event);
                          }}
                          className={cn(
                            "p-2.5 rounded-xl border transition-all text-left flex flex-col gap-1 shadow-lg hover:scale-[1.02]",
                            event.color === 'cron_job'
                              ? "bg-gradient-to-br from-purple-950/30 to-indigo-950/30 border-purple-500/40 text-purple-200 hover:bg-purple-900/40 hover:border-purple-400 shadow-[0_0_12px_rgba(168,85,247,0.2)]"
                              : event.all_day 
                                ? "bg-shogun-gold/10 border-shogun-gold/30 text-shogun-gold hover:bg-shogun-gold/15"
                                : "bg-shogun-blue/10 border-shogun-blue/30 text-shogun-blue hover:bg-shogun-blue/15"
                          )}
                        >
                          <span className="text-xs font-bold leading-snug line-clamp-2">{event.title}</span>
                          <span className="text-[9px] font-mono opacity-80 flex items-center gap-1 font-bold">
                            <Clock className="w-2.5 h-2.5" />
                            {event.all_day ? 'All Day' : `${new Date(event.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })} - ${new Date(event.end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false })}`}
                          </span>
                          {event.location && (
                            <span className="text-[9px] opacity-80 flex items-center gap-1 truncate font-medium">
                              <MapPin className="w-2.5 h-2.5 shrink-0" />
                              {event.location}
                            </span>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* ── DAY VIEW ── */}
        {viewMode === 'day' && (
          <div className="flex-1 flex min-h-0 divide-x divide-shogun-border/20">
            {/* Left timeline section */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-shogun-border/20 pb-3 shrink-0">
                <span className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Day Agenda</span>
                <span className="text-xs text-shogun-subdued font-bold font-mono">
                  {getEventsForDay(currentDate).length} Events scheduled
                </span>
              </div>

              {getEventsForDay(currentDate).length === 0 ? (
                <div className="h-48 flex flex-col items-center justify-center text-shogun-subdued space-y-2 opacity-50">
                  <Calendar className="w-8 h-8" />
                  <p className="text-xs italic">No directives scheduled for this sector.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {getEventsForDay(currentDate).map(event => (
                    <div
                      key={event.id}
                      onClick={() => openViewModal(event)}
                      className={cn(
                        "p-4 rounded-2xl border transition-all cursor-pointer hover:bg-shogun-card/45 flex flex-col md:flex-row md:items-center justify-between gap-4",
                        event.color === 'cron_job'
                          ? "bg-gradient-to-r from-purple-950/20 to-indigo-950/20 border-purple-500/30 text-purple-200 hover:from-purple-950/35 hover:to-indigo-950/35"
                          : event.all_day 
                            ? "bg-shogun-gold/5 border-shogun-gold/20 text-shogun-gold"
                            : "bg-shogun-blue/5 border-shogun-blue/20 text-shogun-blue"
                      )}
                    >
                      <div className="space-y-1.5 flex-1 min-w-0">
                        <h4 className="text-sm font-bold text-shogun-text leading-snug">{event.title}</h4>
                        
                        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-shogun-subdued font-medium">
                          <span className="flex items-center gap-1">
                            <Clock className="w-3 h-3 text-shogun-blue" />
                            {event.all_day ? 'All Day' : `${new Date(event.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} - ${new Date(event.end).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`}
                          </span>
                          
                          {event.location && (
                            <span className="flex items-center gap-1 truncate max-w-xs">
                              <MapPin className="w-3 h-3 text-shogun-gold" />
                              {event.location}
                            </span>
                          )}
                        </div>

                        {event.description && (
                          <p className="text-xs text-shogun-subdued font-mono truncate max-w-2xl mt-1.5 opacity-90">
                            {event.description}
                          </p>
                        )}
                      </div>

                      <div className="flex gap-2 self-end md:self-center shrink-0">
                        {event.color === 'cron_job' ? (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              navigate('/shogun?tab=operations');
                            }}
                            className="px-3 py-1.5 text-[10px] font-bold border border-purple-500/30 text-purple-300 hover:text-purple-200 hover:border-purple-500/50 rounded-lg hover:bg-purple-500/10 transition-all"
                          >
                            Configure
                          </button>
                        ) : (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              openViewModal(event);
                              switchEditMode();
                            }}
                            disabled={!account.perm_edit_events}
                            className="px-3 py-1.5 text-[10px] font-bold border border-shogun-border text-shogun-subdued hover:text-shogun-text rounded-lg hover:bg-white/5 transition-all disabled:opacity-40"
                          >
                            Edit
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── EVENT VIEW / EDIT / CREATE MODAL ─────────────────────── */}
      {showEventModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/75 backdrop-blur-md"
            onClick={() => { if (!submittingEvent) setShowEventModal(false); }}
          />

          <div className="relative w-full max-w-lg bg-[#09090e] border border-shogun-border rounded-2xl flex flex-col shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
            {/* Modal Header */}
            <div className="flex justify-between items-center p-5 border-b border-shogun-border/30 bg-[#0a0a0f]/40">
              <h3 className="text-sm font-bold text-shogun-text uppercase tracking-widest flex items-center gap-2">
                <Calendar className="w-4 h-4 text-shogun-blue" />
                {modalMode === 'create' && 'Schedule Event'}
                {modalMode === 'view' && 'Event Parameters'}
                {modalMode === 'edit' && 'Edit Event'}
              </h3>
              <button
                disabled={submittingEvent}
                onClick={() => setShowEventModal(false)}
                className="p-1 text-shogun-subdued hover:text-shogun-text transition-colors disabled:opacity-40"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            {modalMode === 'view' && selectedEvent ? (
              <div className="p-6 space-y-6">
                <div className="space-y-2">
                  <h2 className="text-lg font-bold text-shogun-text leading-snug">{selectedEvent.title}</h2>
                  
                  <div className="flex flex-col gap-2.5 text-xs text-shogun-subdued mt-2 font-medium">
                    <div className="flex items-center gap-2">
                      <Clock className="w-4 h-4 text-shogun-blue" />
                      <span>
                        {selectedEvent.all_day 
                          ? `${new Date(selectedEvent.start).toLocaleDateString()} (All Day)`
                          : `${new Date(selectedEvent.start).toLocaleString()} – ${new Date(selectedEvent.end).toLocaleString()}`
                        }
                      </span>
                    </div>

                    {selectedEvent.location && (
                      <div className="flex items-center gap-2">
                        <MapPin className="w-4 h-4 text-shogun-gold" />
                        <span className="text-shogun-text">{selectedEvent.location}</span>
                      </div>
                    )}
                  </div>
                </div>

                {selectedEvent.description && (
                  <div className="space-y-1.5 p-4 rounded-xl border border-shogun-border/20 bg-[#050508]/80">
                    <span className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest block">Description</span>
                    <p className="text-xs text-shogun-text font-mono whitespace-pre-wrap leading-relaxed">
                      {selectedEvent.description}
                    </p>
                  </div>
                )}

                {/* Footer Controls for View Mode */}
                <div className="flex justify-between items-center pt-2 border-t border-shogun-border/20 gap-3">
                  {selectedEvent.color === 'cron_job' ? (
                    <>
                      <div />
                      <button
                        onClick={() => {
                          setShowEventModal(false);
                          navigate('/shogun?tab=operations');
                        }}
                        className="flex items-center gap-1.5 px-5 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold rounded-lg text-xs uppercase tracking-wider transition-all shadow-[0_0_10px_rgba(147,51,234,0.3)]"
                      >
                        <Settings className="w-4 h-4" /> Configure Cron Job
                      </button>
                    </>
                  ) : (
                    <>
                      {account.perm_delete_events ? (
                        <button
                          onClick={handleDeleteEvent}
                          disabled={submittingEvent}
                          className="flex items-center gap-1.5 px-4 py-2 border border-red-500/20 text-red-400/80 hover:text-red-400 hover:bg-red-500/10 rounded-lg text-xs font-bold transition-all disabled:opacity-40"
                        >
                          <Trash2 className="w-4 h-4" /> Delete Event
                        </button>
                      ) : <div />}

                      {account.perm_edit_events && (
                        <button
                          onClick={switchEditMode}
                          className="flex items-center gap-1.5 px-5 py-2 bg-shogun-blue hover:bg-shogun-blue/90 text-white font-bold rounded-lg text-xs uppercase tracking-wider transition-all"
                        >
                          <Edit3 className="w-4 h-4" /> Edit Event
                        </button>
                      )}
                    </>
                  )}
                </div>
              </div>
            ) : (
              /* Create/Edit Form Mode */
              <form onSubmit={handleCreateOrUpdateEvent} className="p-5 flex-1 flex flex-col gap-4 overflow-y-auto">
                {formError && (
                  <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-500 rounded-lg text-xs font-semibold flex items-center gap-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{formError}</span>
                  </div>
                )}

                {/* Title */}
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Event Title *</label>
                  <input
                    type="text"
                    required
                    placeholder="Brief description of event"
                    value={eventTitle}
                    onChange={e => setEventTitle(e.target.value)}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                  />
                </div>

                {/* Datetime range */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Start Date & Time *</label>
                    <input
                      type="datetime-local"
                      required
                      value={eventStart}
                      onChange={e => setEventStart(e.target.value)}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">End Date & Time *</label>
                    <input
                      type="datetime-local"
                      required
                      value={eventEnd}
                      onChange={e => setEventEnd(e.target.value)}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono"
                    />
                  </div>
                </div>

                {/* All day & Location */}
                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="allDayCheck"
                      checked={eventAllDay}
                      onChange={e => setEventAllDay(e.target.checked)}
                      className="rounded border-shogun-border text-shogun-blue focus:ring-shogun-blue bg-[#050508]"
                    />
                    <label htmlFor="allDayCheck" className="text-xs text-shogun-text select-none cursor-pointer">
                      All Day Event
                    </label>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Location</label>
                    <input
                      type="text"
                      placeholder="e.g. Conference Room A, Virtual Link"
                      value={eventLocation}
                      onChange={e => setEventLocation(e.target.value)}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                    />
                  </div>
                </div>

                {/* Description */}
                <div className="space-y-1.5">
                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Description</label>
                  <textarea
                    rows={4}
                    placeholder="Enter additional details..."
                    value={eventDescription}
                    onChange={e => setEventDescription(e.target.value)}
                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono resize-y"
                  />
                </div>

                {/* Form submit button */}
                <div className="flex gap-3 mt-2">
                  <button
                    type="button"
                    disabled={submittingEvent}
                    onClick={() => {
                      if (modalMode === 'edit') {
                        setModalMode('view');
                      } else {
                        setShowEventModal(false);
                      }
                    }}
                    className="flex-1 py-3 border border-shogun-border text-shogun-subdued hover:text-shogun-text font-bold rounded-lg text-sm uppercase tracking-wider transition-all disabled:opacity-40"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submittingEvent || !eventTitle || !eventStart || !eventEnd}
                    className="flex-1 flex items-center justify-center gap-2 py-3 bg-shogun-blue hover:bg-shogun-blue/90 disabled:opacity-40 text-white font-bold rounded-lg text-sm uppercase tracking-wider transition-all"
                  >
                    {submittingEvent ? (
                      <><RefreshCw className="w-4 h-4 animate-spin" /> Synchronizing CalDAV…</>
                    ) : (
                      modalMode === 'edit' ? 'Update Event' : 'Create Event'
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
