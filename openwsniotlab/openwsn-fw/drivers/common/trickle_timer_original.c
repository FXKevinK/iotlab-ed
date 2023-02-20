
/**
\brief

\author Dzaky Zakiyal Fawwaz <dzakybd@gmail.com>
*/

#include "opendefs.h"
#include "opentimers.h"
#include "IEEE802154E.h"
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
#include "neighbors.h"
#include "packetfunctions.h"
#include "openqueue.h"

//=========================== define ==========================================

//=========================== variables =======================================

opentrickletimers_vars_t opentrickletimers_vars;
opentrickletimers_debug_t opentrickletimers_debug;

//=========================== prototypes ======================================

void opentrickletimers_t_callback(opentimers_id_t id);
void opentrickletimers_i_callback(opentimers_id_t id);
void opentrickletimers_schedule_event_at_t_and_i(void);
void opentrickletimers_start_next_interval(void);
void opentrickletimers_update_qtable(void);
void opentrickletimers_log_result(bool is_reset);
void opentrickletimers_cancel_timers(void);
uint16_t opentrickletimers_getOpsMC(void);
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
bool opentrickletimers_initialize(opentimers_id_t id, opentimers_cbt cb)
{
    INTERRUPT_DECLARATION();

    if (id < 0 || MAX_NUM_TIMERS <= id)
    {
        return FALSE;
    }

    if (cb == NULL)
    {
        return FALSE;
    }

    DISABLE_INTERRUPTS();

    opentrickletimers_vars.Imin = (DEFAULT_DIO_IMIN_MS / 1000) * schedule_getSlotframeDuration();
    opentrickletimers_vars.Imax = DEFAULT_DIO_INTERVAL_DOUBLINGS;
    opentrickletimers_vars.max_interval = opentrickletimers_vars.Imin * (1 << DEFAULT_DIO_INTERVAL_DOUBLINGS);
    opentrickletimers_vars.K = DEFAULT_DIO_REDUNDANCY_CONSTANT;

    opentrickletimers_vars.I = 0;
    opentrickletimers_vars.callback = cb;
    opentrickletimers_vars.isUsed = TRUE;
    opentrickletimers_vars.isRunning = FALSE;
    opentrickletimers_vars.is_dio_sent = FALSE;
    opentrickletimers_vars.Nstates = 0;
    opentrickletimers_vars.Ncells = 0;
    opentrickletimers_vars.DIOtransmit = 0;
    opentrickletimers_vars.used = 0;
    opentrickletimers_vars.Nnbr = 0;
    opentrickletimers_vars.T = 0;
    opentrickletimers_vars.C = 0;

    opentrickletimers_vars.Nreset = 0;
    opentrickletimers_vars.pbusy = 0;
    opentrickletimers_vars.preset = 0;
    opentrickletimers_vars.pstable = 0;
    opentrickletimers_vars.ptransmit = 0;
    opentrickletimers_vars.pfailed = 0;
    opentrickletimers_vars.psent = 0;
    opentrickletimers_vars.pqu = 0;
    opentrickletimers_vars.ops = 0;

    opentrickletimers_vars.sc_at_i = id;
    opentrickletimers_vars.sc_at_t = opentimers_create(TIMER_GENERAL_PURPOSE, TASKPRIO_RPL);
    opentrickletimers_vars.sc_at_start_t = opentimers_create(TIMER_GENERAL_PURPOSE, TASKPRIO_RPL);
    opentrickletimers_vars.sc_at_end_t = opentimers_create(TIMER_GENERAL_PURPOSE, TASKPRIO_RPL);

    if (
        (opentrickletimers_vars.sc_at_i < 0 || MAX_NUM_TIMERS <= opentrickletimers_vars.sc_at_i) ||
        (opentrickletimers_vars.sc_at_t < 0 || MAX_NUM_TIMERS <= opentrickletimers_vars.sc_at_t) ||
    )
    {
        LOG_CRITICAL(COMPONENT_OPENTRICKLETIMERS, ERR_NO_FREE_TIMER_OR_QUEUE_ENTRY, 0, 0);
        return FALSE;
    }

    ENABLE_INTERRUPTS();

    return TRUE;
}

uint32_t opentrickletimers_getValue(uint8_t code)
{
    if (code == 0)
        return opentrickletimers_vars.I;
    else if (code == 1)
        return opentrickletimers_vars.Imin;
    return -1;
}

void opentrickletimers_schedule_event_at_t_and_i(void)
{
    uint32_t rand_num;
    uint32_t half_interval;

    INTERRUPT_DECLARATION();

    if ((opentrickletimers_vars.sc_at_i < 0 || MAX_NUM_TIMERS <= opentrickletimers_vars.sc_at_i))
    {
        return;
    }

    DISABLE_INTERRUPTS();

    half_interval = opentrickletimers_vars.I / 2;

    opentrickletimers_vars.t_start = half_interval;
    opentrickletimers_vars.t_end = opentrickletimers_vars.I;

    rand_num = openrandom_get16b();
    // add/subtract with 20ms, to avoid same value of T with t_start or t_end
    opentrickletimers_vars.T = (rand_num % ((opentrickletimers_vars.t_end) - (opentrickletimers_vars.t_start) + 1)) + (opentrickletimers_vars.t_start);

    opentrickletimers_vars.ops = opentrickletimers_getOpsMC();

    if (opentrickletimers_vars.T < 0 || opentrickletimers_vars.t_start < 0 || opentrickletimers_vars.I < 0)
    {
        LOG_CRITICAL(COMPONENT_OPENTRICKLETIMERS, ERR_TIMER_MINUS, 0, 0);
    }

    opentimers_scheduleIn(
        opentrickletimers_vars.sc_at_t,
        opentrickletimers_vars.T,
        TIME_MS,
        TIMER_ONESHOT,
        opentrickletimers_t_callback);

    opentimers_scheduleIn(
        opentrickletimers_vars.sc_at_i,
        opentrickletimers_vars.I,
        TIME_MS,
        TIMER_ONESHOT,
        opentrickletimers_i_callback);

    ENABLE_INTERRUPTS();
}

void opentrickletimers_cancel_timers(void)
{
    opentimers_cancel(opentrickletimers_vars.sc_at_i);
    opentimers_cancel(opentrickletimers_vars.sc_at_t);
    opentimers_cancel(opentrickletimers_vars.sc_at_start_t);
    opentimers_cancel(opentrickletimers_vars.sc_at_end_t);
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

    opentrickletimers_cancel_timers();

    opentrickletimers_vars.Nstates += 1;
    opentrickletimers_vars.C = 0;
    opentrickletimers_schedule_event_at_t_and_i();

    ENABLE_INTERRUPTS();
}

void opentrickletimers_start(opentimers_id_t id)
{
    INTERRUPT_DECLARATION();
    DISABLE_INTERRUPTS();

    opentrickletimers_vars.isRunning = TRUE;
    opentrickletimers_vars.I = opentrickletimers_vars.Imin;
    opentrickletimers_start_next_interval();

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
        return FALSE;
    }

    if (!opentrickletimers_vars.isRunning)
    {
        return FALSE;
    }

    if ((opentrickletimers_vars.sc_at_i < 0 || MAX_NUM_TIMERS <= opentrickletimers_vars.sc_at_i))
    {
        return FALSE;
    }

    DISABLE_INTERRUPTS();

    opentrickletimers_vars.isRunning = FALSE;
    opentrickletimers_vars.callback = NULL;

    opentrickletimers_cancel_timers();

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
        return FALSE;
    }

    DISABLE_INTERRUPTS();

    opentrickletimers_vars.C += 1;

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
        return FALSE;
    }

    if (!opentrickletimers_vars.isRunning)
    {
        return FALSE;
    }

    DISABLE_INTERRUPTS();

    opentrickletimers_vars.Nreset += 1;
    opentrickletimers_log_result(TRUE);
    opentrickletimers_vars.I = opentrickletimers_vars.Imin;
    opentrickletimers_start_next_interval();

    ENABLE_INTERRUPTS();

    return TRUE;
}

//=========================== private ==========================================

uint16_t opentrickletimers_getOpsMC(void)
{
    uint16_t ops = EMPTY_16;
    slotinfo_element_t minimal_cell;

    INTERRUPT_DECLARATION();
    DISABLE_INTERRUPTS();
    schedule_getSlotInfo(SCHEDULE_MINIMAL_6TISCH_SLOTOFFSET, &minimal_cell);
    if (minimal_cell.found == TRUE && minimal_cell.channelOffset == 0)
        ops = minimal_cell.allOps;
    ENABLE_INTERRUPTS();

    return ops;
}

void opentrickletimers_i_callback(opentimers_id_t id)
{
    INTERRUPT_DECLARATION();
    DISABLE_INTERRUPTS();

    opentrickletimers_log_result(FALSE);

    opentrickletimers_vars.I *= 2;
    if (opentrickletimers_vars.max_interval < opentrickletimers_vars.I)
        opentrickletimers_vars.I = opentrickletimers_vars.max_interval;
    opentrickletimers_start_next_interval();

    ENABLE_INTERRUPTS();
}

void opentrickletimers_log_result(bool is_reset)
{

    if (idmanager_getIsDAGroot() == TRUE)
    {
        return;
    }

    opentrickletimers_debug.state = opentrickletimers_vars.Nstates;
    opentrickletimers_debug.Nreset = opentrickletimers_vars.Nreset;
    opentrickletimers_debug.counter = opentrickletimers_vars.C;
    opentrickletimers_debug.k = opentrickletimers_vars.K;
    opentrickletimers_debug.Nnbr = opentrickletimers_vars.Nnbr;
    opentrickletimers_debug.used = opentrickletimers_vars.used;
    opentrickletimers_debug.Ncells = opentrickletimers_vars.Ncells;
    opentrickletimers_debug.preset = (uint16_t)(opentrickletimers_vars.preset * float_multiplier);
    opentrickletimers_debug.pstable = (uint16_t)(opentrickletimers_vars.pstable * float_multiplier);
    opentrickletimers_debug.ptransmit = (uint16_t)(opentrickletimers_vars.ptransmit * float_multiplier);
    openserial_print_exp(COMPONENT_OPENTRICKLETIMERS, ERR_EXPERIMENT, (uint8_t *)&opentrickletimers_debug, sizeof(opentrickletimers_debug_t));
}

void opentrickletimers_t_callback(opentimers_id_t id)
{
    INTERRUPT_DECLARATION();
    DISABLE_INTERRUPTS();
    if (
        opentrickletimers_vars.isRunning == TRUE &&
        opentrickletimers_vars.isUsed == TRUE &&
        opentrickletimers_vars.callback != NULL)
    {
        // reset_is_dio_sent
        opentrickletimers_vars.is_dio_sent = FALSE;
        if (opentrickletimers_vars.C < opentrickletimers_vars.K)
            opentrickletimers_vars.is_dio_sent = TRUE;
    }

    if (opentrickletimers_vars.is_dio_sent)
    {
        opentrickletimers_vars.callback(id);
        opentrickletimers_vars.DIOtransmit += 1;
    }

    ENABLE_INTERRUPTS();
}