/**
\brief

\author Dzaky Zakiyal Fawwaz <dzakybd@gmail.com>
*/

#include "opendefs.h"
#include "opentimers.h"
#include "sctimer.h"
#include "debugpins.h"
#include "scheduler.h"
#include "openserial.h"
#include "opentrickletimers.h"
#include "openrandom.h"
#include "opendefs.h"
#include "schedule.h"
#include "icmpv6rpl.h"
#include "idmanager.h"

//=========================== define ==========================================

//=========================== variables =======================================

opentrickletimers_vars_t opentrickletimers_vars;

//=========================== prototypes ======================================

void opentrickletimers_t_callback(opentimers_id_t id);
void opentrickletimers_start_t_callback(opentimers_id_t id);
void opentrickletimers_end_t_callback(opentimers_id_t id);
void opentrickletimers_i_callback(opentimers_id_t id);
void opentrickletimers_end_t_i_callback(opentimers_id_t id);
void opentrickletimers_schedule_event_at_t_and_i(void);
void opentrickletimers_start_next_interval(void);

//=========================== public ==========================================

/**

opentrickletimers_vars 초기화

 */
void opentrickletimers_init(void)
{
    memset(&opentrickletimers_vars, 0, sizeof(opentrickletimers_vars_t));
}

/**

opentrickletimer 생성 함수
timer_id를 이용해 opentimers를 생성한다.

 */
opentimers_id_t opentrickletimers_create(uint8_t timer_id,
                                         uint8_t task_prio)
{
    return opentimers_create(timer_id, task_prio);
}

/**
시작할 떄 한 번만 호출

opentrickletimers가 만료됐을 때 실행될 callback 함수
현재 틱 카운터를 이용해, 만료된 모든 opentrickletimer의 콜백 함수를 실행시키며
interval을 재설정 후 다시 실행시킨다.

 */
bool opentrickletimers_initialize(opentimers_id_t id,
                                  uint32_t Imin,
                                  uint8_t Imax,
                                  uint8_t k_max,
                                  opentimers_cbt cb)
{
    INTERRUPT_DECLARATION();

    if (id < 0 || MAX_NUM_TIMERS <= id)
    {
        return FALSE;
    }

    if (cb == NULL)
    {
        // 잘못된 call back
        return FALSE;
    }

    if (Imin < 1 || Imax < 1)
    {
        // 잘못된 Imin 또는 Imax
        return FALSE;
    }

    DISABLE_INTERRUPTS();

    opentrickletimers_vars.Imin = Imin;
    opentrickletimers_vars.Imax = Imax;
    opentrickletimers_vars.max_interval = Imin * (1 << Imax);

    opentrickletimers_vars.K = k_max;
    opentrickletimers_vars.m = 0;
    opentrickletimers_vars.C = 0;
    opentrickletimers_vars.I = 0;
    opentrickletimers_vars.start_ops = -1;
    opentrickletimers_vars.end_ops = -1;
    opentrickletimers_vars.Ncells = -1;
    opentrickletimers_vars.is_dio_sent = FALSE;
    opentrickletimers_vars.Nstates = 1;
    opentrickletimers_vars.pfree = 1;
    opentrickletimers_vars.poccupancy = 0;
    opentrickletimers_vars.Nreset = 0;
    opentrickletimers_vars.DIOsurpress = 0;
    opentrickletimers_vars.DIOtransmit = 0;
    opentrickletimers_vars.t_pos = 0;
    opentrickletimers_vars.preset = 0;
    opentrickletimers_vars.pstable = 1;

    opentrickletimers_vars.callback = cb;
    opentrickletimers_vars.isUsed = TRUE;
    opentrickletimers_vars.isRunning = FALSE;

    opentrickletimers_vars.sc_at_i = id;
    opentrickletimers_vars.sc_at_t = opentimers_create(TIMER_GENERAL_PURPOSE, TASKPRIO_RPL);
    opentrickletimers_vars.sc_at_start_t = opentimers_create(TIMER_GENERAL_PURPOSE, TASKPRIO_RPL);
    opentrickletimers_vars.sc_at_end_t = opentimers_create(TIMER_GENERAL_PURPOSE, TASKPRIO_RPL);

    if (
        (opentrickletimers_vars.sc_at_i < 0 || MAX_NUM_TIMERS <= opentrickletimers_vars.sc_at_i) ||
        (opentrickletimers_vars.sc_at_t < 0 || MAX_NUM_TIMERS <= opentrickletimers_vars.sc_at_t) ||
        (opentrickletimers_vars.sc_at_start_t < 0 || MAX_NUM_TIMERS <= opentrickletimers_vars.sc_at_start_t) ||
        (opentrickletimers_vars.sc_at_end_t < 0 || MAX_NUM_TIMERS <= opentrickletimers_vars.sc_at_end_t))
    {
        return FALSE;
    }

    ENABLE_INTERRUPTS();

    return TRUE;
}

uint32_t opentrickletimers_getValue(uint8_t code)
{
    if (code == 0)
    {
        return opentrickletimers_vars.I;
    }
    else if (code == 1)
    {
        return opentrickletimers_vars.Imin;
    }
    return -1;
}

void opentrickletimers_schedule_event_at_t_and_i(void)
{

    uint32_t t_range;
    uint16_t l_e;
    uint32_t rand_num;

    INTERRUPT_DECLARATION();

    if ((opentrickletimers_vars.sc_at_i < 0 || MAX_NUM_TIMERS <= opentrickletimers_vars.sc_at_i))
    {
        return;
    }

    DISABLE_INTERRUPTS();

    opentrickletimers_vars.t_min = opentrickletimers_vars.I / 2;
    opentrickletimers_vars.t_max = opentrickletimers_vars.I;
    t_range = opentrickletimers_vars.t_max - opentrickletimers_vars.t_min;
    l_e = SLOTFRAME_LENGTH * SLOTDURATION;
    opentrickletimers_vars.Ncells = t_range / l_e;
    if (opentrickletimers_vars.Ncells < 1)
    {
        opentrickletimers_vars.Ncells = 1;
    }
    rand_num = openrandom_get16b();
    opentrickletimers_vars.T = (rand_num % (opentrickletimers_vars.t_max - opentrickletimers_vars.t_min + 1)) + opentrickletimers_vars.t_min;
    opentrickletimers_vars.t_pos = (float)opentrickletimers_vars.T / opentrickletimers_vars.I;

    opentimers_scheduleIn(
        opentrickletimers_vars.sc_at_t,
        opentrickletimers_vars.T,
        TIME_MS,
        TIMER_ONESHOT,
        opentrickletimers_t_callback);

    opentimers_scheduleIn(
        opentrickletimers_vars.sc_at_start_t,
        opentrickletimers_vars.t_min,
        TIME_MS,
        TIMER_ONESHOT,
        opentrickletimers_start_t_callback);

    if (opentrickletimers_vars.t_max < opentrickletimers_vars.I)
    {
        opentimers_scheduleIn(
            opentrickletimers_vars.sc_at_end_t,
            opentrickletimers_vars.t_max,
            TIME_MS,
            TIMER_ONESHOT,
            opentrickletimers_end_t_callback);

        opentimers_scheduleIn(
            opentrickletimers_vars.sc_at_i,
            opentrickletimers_vars.I,
            TIME_MS,
            TIMER_ONESHOT,
            opentrickletimers_i_callback);
    }
    else
    {
        opentimers_scheduleIn(
            opentrickletimers_vars.sc_at_i,
            opentrickletimers_vars.I,
            TIME_MS,
            TIMER_ONESHOT,
            opentrickletimers_end_t_i_callback);
    }

    ENABLE_INTERRUPTS();
}

void opentrickletimers_start_next_interval(void)
{
    INTERRUPT_DECLARATION();

    if (opentrickletimers_vars.isRunning == FALSE)
    {
        return;
    }

    if (opentrickletimers_vars.isUsed == FALSE)
    {
        return;
    }

    if ((opentrickletimers_vars.sc_at_i < 0 || MAX_NUM_TIMERS <= opentrickletimers_vars.sc_at_i))
    {
        return;
    }

    DISABLE_INTERRUPTS();

    opentrickletimers_vars.C = 0;

    opentimers_cancel(opentrickletimers_vars.sc_at_i);
    opentimers_cancel(opentrickletimers_vars.sc_at_t);
    opentimers_cancel(opentrickletimers_vars.sc_at_start_t);
    opentimers_cancel(opentrickletimers_vars.sc_at_end_t);

    opentrickletimers_schedule_event_at_t_and_i();

    ENABLE_INTERRUPTS();
}

void opentrickletimers_start(opentimers_id_t id)
{
    uint32_t rand_num;

    INTERRUPT_DECLARATION();
    DISABLE_INTERRUPTS();

    opentrickletimers_vars.isRunning = TRUE;
    opentrickletimers_vars.m = 0;

    rand_num = openrandom_get16b();
    opentrickletimers_vars.I = (rand_num % (opentrickletimers_vars.max_interval - opentrickletimers_vars.Imin + 1)) + opentrickletimers_vars.Imin;

    opentrickletimers_start_next_interval();

    // |-------+-----+------------------------------|
    //         T I = Imin                max_interval (Imin*2^Imax)

    ENABLE_INTERRUPTS();
}

/**
 * \brief 파라미터 ID의 트리클 타이머를 캔슬
 */
bool opentrickletimers_stop(opentimers_id_t id)
{

    INTERRUPT_DECLARATION();

    if (id < 0 || MAX_NUM_TIMERS <= id)
    {
        return FALSE;
    }

    if (!opentrickletimers_vars.isUsed)
    {
        // 생성되지 않은 타이머 아이디
        return FALSE;
    }

    if (!opentrickletimers_vars.isRunning)
    {
        // 생성되지 않은 타이머 아이디
        return FALSE;
    }

    if ((opentrickletimers_vars.sc_at_i < 0 || MAX_NUM_TIMERS <= opentrickletimers_vars.sc_at_i))
    {
        return FALSE;
    }

    DISABLE_INTERRUPTS();

    opentrickletimers_vars.isRunning = FALSE;
    opentrickletimers_vars.callback = NULL;

    opentimers_cancel(opentrickletimers_vars.sc_at_i);
    opentimers_cancel(opentrickletimers_vars.sc_at_t);
    opentimers_cancel(opentrickletimers_vars.sc_at_start_t);
    opentimers_cancel(opentrickletimers_vars.sc_at_end_t);

    ENABLE_INTERRUPTS();

    return TRUE;
}

bool opentrickletimers_recvConsistent(opentimers_id_t id)
{

    INTERRUPT_DECLARATION();

    if (id < 0 || MAX_NUM_TIMERS <= id)
    {
        return FALSE;
    }

    if (!opentrickletimers_vars.isUsed)
    {
        // 생성되지 않은 타이머 아이디
        return FALSE;
    }

    DISABLE_INTERRUPTS();

    opentrickletimers_vars.C++;

    ENABLE_INTERRUPTS();

    return TRUE;
}

bool opentrickletimers_reset(opentimers_id_t id)
{
    INTERRUPT_DECLARATION();

    if (id < 0 || MAX_NUM_TIMERS <= id)
    {
        return FALSE;
    }

    if (!opentrickletimers_vars.isUsed)
    {
        // 생성되지 않은 타이머 아이디
        return FALSE;
    }

    if (!opentrickletimers_vars.isRunning)
    {
        // 생성되지 않은 타이머 아이디
        return FALSE;
    }

    DISABLE_INTERRUPTS();

    opentrickletimers_vars.m = 0;
    opentrickletimers_vars.Nreset += 1;
    opentrickletimers_vars.preset = (float)opentrickletimers_vars.Nreset / opentrickletimers_vars.Nstates;
    opentrickletimers_vars.pstable = 1 - opentrickletimers_vars.preset;

    if (opentrickletimers_vars.Imin < opentrickletimers_vars.I)
    {
        opentrickletimers_vars.I = opentrickletimers_vars.Imin;
        opentrickletimers_start_next_interval();
    }

    ENABLE_INTERRUPTS();

    return TRUE;
}

//=========================== private ==========================================

void opentrickletimers_start_t_callback(opentimers_id_t id)
{
    slotinfo_element_t minimal_cell;

    INTERRUPT_DECLARATION();
    DISABLE_INTERRUPTS();

    schedule_getSlotInfo(SCHEDULE_MINIMAL_6TISCH_SLOTOFFSET, &minimal_cell);
    opentrickletimers_vars.start_ops = -1;
    if (minimal_cell.found == TRUE && minimal_cell.channelOffset == 0)
    {
        opentrickletimers_vars.start_ops = minimal_cell.allOps;
    }
    ENABLE_INTERRUPTS();
}

void opentrickletimers_end_t_callback(opentimers_id_t id)
{
    slotinfo_element_t minimal_cell;

    INTERRUPT_DECLARATION();
    DISABLE_INTERRUPTS();

    schedule_getSlotInfo(SCHEDULE_MINIMAL_6TISCH_SLOTOFFSET, &minimal_cell);
    opentrickletimers_vars.end_ops = -1;
    if (minimal_cell.found == TRUE && minimal_cell.channelOffset == 0)
    {
        opentrickletimers_vars.end_ops = minimal_cell.allOps;
    }
    ENABLE_INTERRUPTS();
}

void opentrickletimers_i_callback(opentimers_id_t id)
{
    uint16_t used = -1;
    float occ = -1;
    uint16_t dio_sent;

    INTERRUPT_DECLARATION();
    DISABLE_INTERRUPTS();
    if (opentrickletimers_vars.start_ops >= 0 && opentrickletimers_vars.end_ops >= 0)
    {
        dio_sent = icmpv6rpl_getdioSent() * opentrickletimers_vars.is_dio_sent;
        used = (opentrickletimers_vars.end_ops - opentrickletimers_vars.start_ops) - dio_sent;
        if (used < 0)
        {
            used = 0;
        }

        if (used <= opentrickletimers_vars.Ncells)
        {
            occ = (float)used / opentrickletimers_vars.Ncells;
            opentrickletimers_vars.poccupancy = occ;
            opentrickletimers_vars.pfree = 1.0 - occ;
        }
    }

    if (opentrickletimers_vars.is_dio_sent)
    {
        opentrickletimers_vars.DIOtransmit += 1;
    }
    else
    {
        opentrickletimers_vars.DIOsurpress += 1;
    }

    icmpv6rpl_setdioSent(FALSE);
    opentrickletimers_vars.is_dio_sent = FALSE;

    opentrickletimers_vars.I *= 2;
    opentrickletimers_vars.m += 1;
    opentrickletimers_vars.Nstates += 1;
    if (opentrickletimers_vars.max_interval < opentrickletimers_vars.I)
    {
        opentrickletimers_vars.I = opentrickletimers_vars.max_interval;
        opentrickletimers_vars.m = opentrickletimers_vars.Imax;
    }

    opentrickletimers_start_next_interval();

    ENABLE_INTERRUPTS();
}

void opentrickletimers_end_t_i_callback(opentimers_id_t id)
{
    opentrickletimers_end_t_callback(opentrickletimers_vars.sc_at_end_t);
    opentrickletimers_i_callback(opentrickletimers_vars.sc_at_i);
}

/**

opentrickletimers가 만료됐을 때 실행될 callback 함수
현재 틱 카운터를 이용해, 만료된 모든 opentrickletimer의 콜백 함수를 실행시키며
interval을 재설정 후 다시 실행시킨다.

 */
void opentrickletimers_t_callback(opentimers_id_t id)
{
    INTERRUPT_DECLARATION();
    DISABLE_INTERRUPTS();
    // opentrickletimer 배열에서 만료된 trickletimer를 확인
    if (
        opentrickletimers_vars.isRunning == TRUE &&
        opentrickletimers_vars.isUsed == TRUE &&
        opentrickletimers_vars.callback != NULL)
    {
        icmpv6rpl_setdioSent(FALSE);
        opentrickletimers_vars.is_dio_sent = FALSE;

        // C가 K보다 작을 때만 callback 실행 또는 K가 0일 때 해당 기능 Disable (항상 callback 실행)
        if (opentrickletimers_vars.C < opentrickletimers_vars.K ||
            opentrickletimers_vars.K == 0)
        {
            opentrickletimers_vars.is_dio_sent = TRUE;
            opentrickletimers_vars.callback(id);
        }
    }
    ENABLE_INTERRUPTS();
}
