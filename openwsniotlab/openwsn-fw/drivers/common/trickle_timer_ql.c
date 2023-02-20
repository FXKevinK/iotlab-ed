
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
void opentrickletimers_calculate_k(void);
void opentrickletimers_update_qtable(void);
void opentrickletimers_log_result(bool is_reset);
void opentrickletimers_cancel_timers(void);
void opentrickletimers_calculate_ptransmit(void);
void opentrickletimers_calculate_preset(void);
void opentrickletimers_calculate_multiple_p(void);
void opentrickletimers_calculate_pbusy(void);
void opentrickletimers_calculate_psent(void);
void opentrickletimers_calculate_pqu(void);
void opentrickletimers_assert_p(float p, uint8_t code);
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

#if use_qtrickle == TRUE
    opentrickletimers_vars.reward = 0;

    opentrickletimers_vars.current_action = 0;
    opentrickletimers_vars.psent_prev = opentrickletimers_vars.psent;
    opentrickletimers_vars.pbusy_prev = opentrickletimers_vars.pbusy;
    opentrickletimers_vars.pqu_prev = opentrickletimers_vars.pqu;
    
    opentrickletimers_vars.epsilon = default_epsilon;
    opentrickletimers_vars.is_explore = FALSE;
    memset(&opentrickletimers_vars.ql_table, 0, sizeof(opentrickletimers_vars.ql_table));
    opentrickletimers_vars.s1 = 0;
    opentrickletimers_vars.s2 = 0;
    opentrickletimers_vars.n_s1 = 0;
    opentrickletimers_vars.n_s2 = 0;

#endif

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

uint32_t opentrickletimers_get_p(uint8_t code)
{
    if (code == 0)
        return opentrickletimers_vars.pbusy * (float_multiplier * 100);
    return -1;
}

bool opentrickletimers_isInTRange(void)
{
    if (
        opentimers_isRunning(opentrickletimers_vars.sc_at_start_t) == FALSE &&
        opentimers_isRunning(opentrickletimers_vars.sc_at_end_t) == TRUE)
        return TRUE;
    return FALSE;
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
#if use_qtrickle == TRUE
    opentrickletimers_vars.t_start = (uint32_t)((float)half_interval * opentrickletimers_vars.ptransmit);
    opentrickletimers_vars.t_end = (uint32_t)((float)half_interval + (opentrickletimers_vars.pstable * half_interval));
#else
    opentrickletimers_vars.t_start = half_interval;
    opentrickletimers_vars.t_end = opentrickletimers_vars.I;
#endif

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
        opentrickletimers_vars.sc_at_start_t,
        opentrickletimers_vars.t_start,
        TIME_MS,
        TIMER_ONESHOT,
        NULL);

    opentimers_scheduleIn(
        opentrickletimers_vars.sc_at_end_t,
        opentrickletimers_vars.t_end,
        TIME_MS,
        TIMER_ONESHOT,
        NULL);

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
#if use_qtrickle == TRUE
    opentrickletimers_calculate_k();
    opentrickletimers_vars.psent_prev = opentrickletimers_vars.psent;
    opentrickletimers_vars.pbusy_prev = opentrickletimers_vars.pbusy;
    opentrickletimers_vars.pqu_prev = opentrickletimers_vars.pqu;
#endif

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
    opentrickletimers_calculate_preset();
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

    opentrickletimers_calculate_multiple_p();
#if use_qtrickle == TRUE
    opentrickletimers_update_qtable();
#endif

    opentrickletimers_log_result(FALSE);

    opentrickletimers_vars.I *= 2;
    if (opentrickletimers_vars.max_interval < opentrickletimers_vars.I)
        opentrickletimers_vars.I = opentrickletimers_vars.max_interval;
    opentrickletimers_start_next_interval();

    ENABLE_INTERRUPTS();
}

void opentrickletimers_calculate_multiple_p(void)
{
    opentrickletimers_calculate_pbusy();
    opentrickletimers_calculate_psent();
    opentrickletimers_calculate_pqu();
}

void opentrickletimers_calculate_preset(void)
{
    opentrickletimers_vars.preset = (float)opentrickletimers_vars.Nreset / opentrickletimers_vars.Nstates;
    opentrickletimers_assert_p(opentrickletimers_vars.preset, 4);
    opentrickletimers_vars.pstable = 1 - opentrickletimers_vars.preset;
}

void opentrickletimers_calculate_ptransmit(void)
{
    opentrickletimers_vars.ptransmit = (float)opentrickletimers_vars.DIOtransmit / opentrickletimers_vars.Nstates;
    opentrickletimers_assert_p(opentrickletimers_vars.ptransmit, 3);
}

void opentrickletimers_calculate_pbusy(void)
{
    uint16_t curr = opentrickletimers_getOpsMC();
    opentrickletimers_vars.Ncells = packetfunctions_mathFloor(((float)opentrickletimers_vars.I / schedule_getSlotframeDuration()));

    if (opentrickletimers_vars.ops == EMPTY_16 || curr == EMPTY_16 || opentrickletimers_vars.Ncells == 0)
    {
        opentrickletimers_vars.pbusy = 0;
        return;
    }

    opentrickletimers_vars.used = curr - opentrickletimers_vars.ops;
    if (opentrickletimers_vars.Ncells < opentrickletimers_vars.used)
        opentrickletimers_vars.Ncells = opentrickletimers_vars.used;
    opentrickletimers_vars.pbusy = (float)opentrickletimers_vars.used / opentrickletimers_vars.Ncells;

    opentrickletimers_assert_p(opentrickletimers_vars.pbusy, 2);
}

void opentrickletimers_calculate_psent(void)
{
    uint16_t failed = icmpv6rpl_get_failed_dio(TRUE, FALSE);
    uint16_t count_ = icmpv6rpl_get_failed_dio(TRUE, TRUE);

    if (count_ == EMPTY_16)
    {
        opentrickletimers_vars.psent = 0;
        opentrickletimers_vars.pfailed = 0;
        return;
    }
    
    opentrickletimers_vars.pfailed = (float) failed / count_;
    opentrickletimers_vars.psent = 1 - opentrickletimers_vars.pfailed;
    opentrickletimers_assert_p(opentrickletimers_vars.psent, 5);
}

void opentrickletimers_calculate_pqu(void)
{

    uint8_t used = openqueue_getUsedQueue();
    opentrickletimers_vars.pqu = (float) used / QUEUELENGTH;
    opentrickletimers_assert_p(opentrickletimers_vars.pqu, 1);
}

void opentrickletimers_assert_p(float p, uint8_t code)
{
    if (p < 0 || p > 1)
        LOG_CRITICAL(COMPONENT_OPENTRICKLETIMERS, ERR_UNDER_OVER_VALUE, code, p * float_multiplier);
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

#if use_qtrickle == TRUE
void opentrickletimers_calculate_k(void)
{
    opentrickletimers_vars.Nnbr = neighbors_getNumNeighbors();
    float temp = DEFAULT_DIO_REDUNDANCY_CONSTANT - 1;
    if (opentrickletimers_vars.Nnbr < temp)
        temp = opentrickletimers_vars.Nnbr;
    temp = temp * opentrickletimers_vars.preset;
    opentrickletimers_vars.K = 1 + packetfunctions_mathCeil(temp);
}
#endif

uint8_t opentrickletimers_prob_to_class(float prob)
{
    if (0 <= prob && prob <= (float)1.0 / 3.0)
        return 0;
    else if ((float)1.0 / 3.0 < prob && prob < (float)2.0 / 3.0)
        return 1;
    else if ((float)2.0 / 3.0 <= prob && prob <= (float)1.0)
        return 2;
    return 2;
}

#if use_qtrickle == TRUE
void opentrickletimers_update_qtable(void)
{
    float next_action_value;
    float next_val0;
    float next_val1;
    float old_value;
    float td_learning;
    float new_value;

    if (opentrickletimers_vars.psent > opentrickletimers_vars.psent_prev || opentrickletimers_vars.psent == 1)
        opentrickletimers_vars.reward = 1;
    else if (opentrickletimers_vars.psent < opentrickletimers_vars.psent_prev || opentrickletimers_vars.psent == 0)
        opentrickletimers_vars.reward = -1;
    else if (opentrickletimers_vars.psent == opentrickletimers_vars.psent_prev)
        opentrickletimers_vars.reward = 0;

    opentrickletimers_vars.s1 = opentrickletimers_prob_to_class(opentrickletimers_vars.pbusy_prev);
    opentrickletimers_vars.s2 = opentrickletimers_prob_to_class(opentrickletimers_vars.pqu_prev);
    opentrickletimers_vars.n_s1 = opentrickletimers_prob_to_class(opentrickletimers_vars.pbusy);
    opentrickletimers_vars.n_s2 = opentrickletimers_prob_to_class(opentrickletimers_vars.pqu);

    old_value = opentrickletimers_vars.ql_table[opentrickletimers_vars.s1][opentrickletimers_vars.s2][opentrickletimers_vars.current_action];

    next_val0 = opentrickletimers_vars.ql_table[opentrickletimers_vars.n_s1][opentrickletimers_vars.n_s2][0];
    next_val1 = opentrickletimers_vars.ql_table[opentrickletimers_vars.n_s1][opentrickletimers_vars.n_s2][1];

    next_action_value = next_val0;
    if (next_val1 > next_val0)
        next_action_value = next_val1;

    td_learning = opentrickletimers_vars.reward + (ql_discount_rate * next_action_value);
    new_value = ((1.0 - ql_learning_rate) * old_value) + (ql_learning_rate * td_learning);
    opentrickletimers_vars.ql_table[opentrickletimers_vars.s1][opentrickletimers_vars.s2][opentrickletimers_vars.current_action] = new_value;
}
#endif

void opentrickletimers_t_callback(opentimers_id_t id)
{
#if use_qtrickle == TRUE
    float val0;
    float val1;
#endif

    INTERRUPT_DECLARATION();
    DISABLE_INTERRUPTS();
    if (
        opentrickletimers_vars.isRunning == TRUE &&
        opentrickletimers_vars.isUsed == TRUE &&
        opentrickletimers_vars.callback != NULL)
    {
        // reset_is_dio_sent
        opentrickletimers_vars.is_dio_sent = FALSE;

#if use_qtrickle == TRUE
        opentrickletimers_vars.is_explore = FALSE;
        if (packetfunctions_random_p(opentrickletimers_vars.epsilon))
        {
            // explore
            opentrickletimers_vars.is_explore = TRUE;
            if (opentrickletimers_vars.C < opentrickletimers_vars.K)
                opentrickletimers_vars.is_dio_sent = TRUE;
        }
        else
        {
            // exploit

            opentrickletimers_vars.s1 = opentrickletimers_prob_to_class(opentrickletimers_vars.pbusy_prev);
            opentrickletimers_vars.s2 = opentrickletimers_prob_to_class(opentrickletimers_vars.pqu_prev);

            val0 = opentrickletimers_vars.ql_table[opentrickletimers_vars.s1][opentrickletimers_vars.s2][0];
            val1 = opentrickletimers_vars.ql_table[opentrickletimers_vars.s1][opentrickletimers_vars.s2][1];

            if (val1 > val0)
                opentrickletimers_vars.is_dio_sent = TRUE;
        }
#else
        if (opentrickletimers_vars.C < opentrickletimers_vars.K)
            opentrickletimers_vars.is_dio_sent = TRUE;
#endif
    }

#if use_qtrickle == TRUE
    opentrickletimers_vars.current_action = 0;
#endif

    if (opentrickletimers_vars.is_dio_sent)
    {
        opentrickletimers_vars.callback(id);
        opentrickletimers_vars.DIOtransmit += 1;
#if use_qtrickle == TRUE
        opentrickletimers_vars.current_action = 1;
#endif
    }
    opentrickletimers_calculate_ptransmit();

    ENABLE_INTERRUPTS();
}