
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
#include "neighbors.h"

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
void opentrickletimers_calculate_k(void);
void opentrickletimers_update_qtable(void);
void opentrickletimers_calculate_epsilon(void);
uint16_t math_ceil(float num);

//=========================== public ==========================================

/**

opentrickletimers_vars 초기화

 */
void opentrickletimers_init(void)
{
    memset(&opentrickletimers_vars, 0, sizeof(opentrickletimers_vars_t));
}

uint16_t math_ceil(float num)
{
    uint16_t inum = (uint16_t)num;
    if (num == (float)inum)
    {
        return inum;
    }
    return inum + 1;
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
        // 잘못된 call back
        return FALSE;
    }

    DISABLE_INTERRUPTS();

    opentrickletimers_vars.Imin = DEFAULT_DIO_IMIN_MS;
    opentrickletimers_vars.Imax = DEFAULT_DIO_IMAX;
    opentrickletimers_vars.max_interval = DEFAULT_DIO_IMIN_MS * DEFAULT_DIO_IMAX;

    opentrickletimers_vars.K = DEFAULT_DIO_REDUNDANCY_CONSTANT;
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

// ok
#if use_qtrickle == TRUE
    opentrickletimers_vars.Nnbr = 0;
    opentrickletimers_vars.DIOtransmit_collision = 0;
    opentrickletimers_vars.ptransmit = 1;
    opentrickletimers_vars.current_action = -1;
    opentrickletimers_vars.ptransmit_collision = 0;
    opentrickletimers_vars.epsilon = default_epsilon;
    opentrickletimers_vars.is_explore = TRUE;
    memset(&opentrickletimers_vars.q_table[0], 0, (DEFAULT_DIO_IMAX + 1) * 2);
#endif

#if adaptive_epsilon == TRUE
    opentrickletimers_vars.total_reward = 0;
    opentrickletimers_vars.prev_total_reward = 0;
    opentrickletimers_vars.epsilon = max_epsilon;
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

    uint8_t lower_bound;
    uint16_t l_e;
    uint32_t t_range;
    uint32_t rand_num;
    uint32_t half_interval;

    INTERRUPT_DECLARATION();

    if ((opentrickletimers_vars.sc_at_i < 0 || MAX_NUM_TIMERS <= opentrickletimers_vars.sc_at_i))
    {
        return;
    }

    DISABLE_INTERRUPTS();

    half_interval = opentrickletimers_vars.I / 2;
// oke
#if use_qtrickle == TRUE
    opentrickletimers_vars.t_min = (uint32_t) ((float) half_interval * (opentrickletimers_vars.ptransmit * opentrickletimers_vars.pfree));
    opentrickletimers_vars.t_max = (uint32_t) ((float) half_interval + (opentrickletimers_vars.pstable * half_interval));
#else
    opentrickletimers_vars.t_min = half_interval;
    opentrickletimers_vars.t_max = opentrickletimers_vars.I;
#endif

    // make sure that I'm scheduling an event in the future
    lower_bound = 20 * 5;
    if(opentrickletimers_vars.t_min < lower_bound){
        opentrickletimers_vars.t_min = lower_bound;
    }
    // make sure there is enough distance between t_min and t_max
    if(opentrickletimers_vars.t_max-opentrickletimers_vars.t_min < lower_bound){
        opentrickletimers_vars.t_min -= lower_bound;
    }

    rand_num = openrandom_get16b();
    // add/subtract with 20ms, to avoid same value of T with t_min or t_max
    opentrickletimers_vars.T = (rand_num % ((opentrickletimers_vars.t_max-20) - (opentrickletimers_vars.t_min+20) + 1)) + (opentrickletimers_vars.t_min+20);
    opentrickletimers_vars.t_pos = (float)opentrickletimers_vars.T / opentrickletimers_vars.I;

    t_range = opentrickletimers_vars.t_max - opentrickletimers_vars.t_min;
    l_e = SLOTFRAME_LENGTH * SLOTDURATION;

    opentrickletimers_vars.Ncells = ((float)t_range / (float)l_e);
    opentrickletimers_vars.Ncells = math_ceil(opentrickletimers_vars.Ncells);
    if (opentrickletimers_vars.Ncells < 1)
    {
        opentrickletimers_vars.Ncells = 1;
    }

    if (opentrickletimers_vars.Ncells < 1)
    {
        opentrickletimers_vars.Ncells = 1;
    }

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

    opentimers_cancel(opentrickletimers_vars.sc_at_i);
    opentimers_cancel(opentrickletimers_vars.sc_at_t);
    opentimers_cancel(opentrickletimers_vars.sc_at_start_t);
    opentimers_cancel(opentrickletimers_vars.sc_at_end_t);

    opentrickletimers_vars.C = 0;
#if use_qtrickle == TRUE
    opentrickletimers_calculate_k();
#endif

    opentrickletimers_schedule_event_at_t_and_i();

    ENABLE_INTERRUPTS();
}

void opentrickletimers_start(opentimers_id_t id)
{
    INTERRUPT_DECLARATION();
    DISABLE_INTERRUPTS();

    opentrickletimers_vars.isRunning = TRUE;
    opentrickletimers_vars.m = 0;

// ok
#if use_qtrickle == TRUE
    opentrickletimers_vars.I = opentrickletimers_vars.Imin;
#else
    uint32_t rand_num = openrandom_get16b();
    opentrickletimers_vars.I = (rand_num % (opentrickletimers_vars.max_interval - opentrickletimers_vars.Imin + 1)) + opentrickletimers_vars.Imin;
#endif

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
    bool fw_dioSent;

    INTERRUPT_DECLARATION();
    DISABLE_INTERRUPTS();

    fw_dioSent = icmpv6rpl_getdioSent();
    if (opentrickletimers_vars.start_ops >= 0 && opentrickletimers_vars.end_ops >= 0)
    {
        dio_sent = fw_dioSent * opentrickletimers_vars.is_dio_sent;
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

// ok
#if use_qtrickle == TRUE
        opentrickletimers_vars.current_action = 1;
        if (fw_dioSent == FALSE)
        {
            opentrickletimers_vars.DIOtransmit_collision += 1;
        }
#endif
    }
    else
    {
        opentrickletimers_vars.DIOsurpress += 1;

// ok
#if use_qtrickle == TRUE
        opentrickletimers_vars.current_action = 0;
#endif
    }

// ok
#if use_qtrickle == TRUE
    opentrickletimers_vars.ptransmit = (float)opentrickletimers_vars.DIOtransmit / (float)opentrickletimers_vars.Nstates;
    opentrickletimers_vars.ptransmit_collision = 0;
    if (opentrickletimers_vars.DIOtransmit > 0)
    {
        opentrickletimers_vars.ptransmit_collision = (float)opentrickletimers_vars.DIOtransmit_collision / (float)opentrickletimers_vars.DIOtransmit;
    }
    opentrickletimers_update_qtable();
#endif

#if adaptive_epsilon == TRUE
    opentrickletimers_vars.total_reward += opentrickletimers_vars.pfree;
    opentrickletimers_calculate_epsilon();
#endif

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

// ok
#if use_qtrickle == TRUE
void opentrickletimers_calculate_k(void)
{
    float temp;

    opentrickletimers_vars.Nnbr = neighbors_getNumNeighbors();
    if (opentrickletimers_vars.Nnbr == 0)
    {
        opentrickletimers_vars.Nnbr = DEFAULT_DIO_REDUNDANCY_CONSTANT;
    }

    temp = DEFAULT_DIO_REDUNDANCY_CONSTANT - 1;
    if (opentrickletimers_vars.Nnbr < temp)
    {
        temp = opentrickletimers_vars.Nnbr;
    }
    temp = temp * opentrickletimers_vars.preset;

    opentrickletimers_vars.K = 1 + math_ceil(temp);
}
#endif

// ok
#if use_qtrickle == TRUE
void opentrickletimers_update_qtable(void)
{
    uint8_t next_m;
    float next_action_value;
    float reward;
    float val0;
    float val1;
    float old_value;
    float td_learning;
    float new_value;

    reward = opentrickletimers_vars.pfree;
    if (opentrickletimers_vars.Imax < (opentrickletimers_vars.m + 1))
    {
        next_m = opentrickletimers_vars.m;
    }
    else
    {
        next_m = opentrickletimers_vars.m + 1;
    }

    val0 = opentrickletimers_vars.q_table[(next_m + 1)];
    val1 = opentrickletimers_vars.q_table[(next_m + 1) * 2];

    next_action_value = val0;
    if (val1 >= val0)
    {
        next_action_value = val1;
    }

    old_value = opentrickletimers_vars.q_table[(opentrickletimers_vars.m + 1) * opentrickletimers_vars.current_action];
    td_learning = (reward + ql_discount_rate * next_action_value) - old_value;

    new_value = (1.0 - ql_learning_rate) * old_value + (ql_learning_rate * td_learning);

    opentrickletimers_vars.q_table[(opentrickletimers_vars.m + 1) * opentrickletimers_vars.current_action] = new_value;
}
#endif

#if use_qtrickle == TRUE
void opentrickletimers_calculate_epsilon(void)
{
    float new_epsilon;
    float average_reward;
    float diff;
    float prev_average_reward;

    average_reward = (float)opentrickletimers_vars.total_reward / opentrickletimers_vars.Nstates;
    diff = average_reward;
    new_epsilon = opentrickletimers_vars.epsilon;

    if (opentrickletimers_vars.Nstates > 1)
    {
        prev_average_reward = (float)opentrickletimers_vars.prev_total_reward / (opentrickletimers_vars.Nstates - 1);
        diff = (float)average_reward - prev_average_reward;

        if (diff > 0)
        {
            // towards exploit
            new_epsilon -= epsilon_delta;
        }
        else
        {
            // towards explore
            new_epsilon += epsilon_delta;
        }
    }

    if (min_epsilon > new_epsilon)
    {
        new_epsilon = min_epsilon;
    }
    if (max_epsilon < new_epsilon)
    {
        new_epsilon = max_epsilon;
    }
    opentrickletimers_vars.epsilon = new_epsilon;
    opentrickletimers_vars.prev_total_reward = opentrickletimers_vars.total_reward;
}
#endif

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
    uint8_t action;
    float val0;
    float val1;
    uint32_t rand_num;
    uint32_t temp;
    uint16_t multiplier;

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

#if use_qtrickle == TRUE

        multiplier = 10000;
        rand_num = (openrandom_get16b() % multiplier);
        action = 0;
        temp = (uint32_t) (opentrickletimers_vars.epsilon * multiplier);
        
        if (rand_num <= temp)
        {
            opentrickletimers_vars.is_explore = TRUE;
            // explore
            if (opentrickletimers_vars.C < opentrickletimers_vars.K ||
                opentrickletimers_vars.K == 0)
            {
                opentrickletimers_vars.is_dio_sent = TRUE;
                opentrickletimers_vars.callback(id);
            }
        }
        else
        {
            opentrickletimers_vars.is_explore = FALSE;
            // exploit
            val0 = opentrickletimers_vars.q_table[(opentrickletimers_vars.m + 1)];
            val1 = opentrickletimers_vars.q_table[(opentrickletimers_vars.m + 1) * 2];

            if (val1 >= val0)
            {
                action = 1;
            }

            if (action == 1)
            {
                opentrickletimers_vars.is_dio_sent = TRUE;
                opentrickletimers_vars.callback(id);
            }
        }
#else
        if (opentrickletimers_vars.C < opentrickletimers_vars.K ||
            opentrickletimers_vars.K == 0)
        {
            opentrickletimers_vars.is_dio_sent = TRUE;
            opentrickletimers_vars.callback(id);
        }
#endif
    }
    ENABLE_INTERRUPTS();
}