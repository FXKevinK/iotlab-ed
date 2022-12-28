/**
\brief trickle timer

\author Jeongbae Park <wjdqo94@gmail.com>
*/

#ifndef __OPENTRICKLETIMERS_H
#define __OPENTRICKLETIMERS_H

#include "opendefs.h"
#include "opentimers.h"

/**
\addtogroup drivers
\{
\addtogroup OpenTrickleTimers
\{
*/

// RFC: 6206 <https://tools.ietf.org/html/rfc6206>

//=========================== define ==========================================

//=========================== typedef =========================================

// |-------+-----+------------------------------|
//         T I = Imin                max_interval (Imin*2^Imax)

//=========================== module variables ================================

typedef struct
{
    uint32_t Imin;           // 최소 타이머 간격 (ex, 100 ms or 100 tics)
    uint8_t Imax;            // 최대 타이머 간격 지수 승 (ex, 16) 최대 타이머 간격 = Imin*2^Imax
    uint8_t K;               // Consistent 메세지 수신 가능 최대 횟수
    uint32_t I;              // 현재 간격
    uint32_t T;              // 현재 간격 내의 임의의 간격 즉, 실제 실행될 타이머 간격
    uint8_t C;               // Consistent 메세지 수신 횟수 카운터
    opentimers_cbt callback; // 타이머 콜백 함수
    bool isUsed;             // 생성된 타이머인지
    bool isRunning;          // 작동 중인 타이머인지
    uint8_t m;
    uint16_t Nreset;
    uint16_t Nstates;
    float preset;
    float pstable;
    float pfree;
    float poccupancy;
    float t_pos;
    uint16_t Ncells;
    uint16_t start_ops;
    uint16_t end_ops;
    uint16_t DIOtransmit;
    uint16_t DIOsurpress;
    uint64_t max_interval;
    bool is_dio_sent;
    uint8_t sc_at_i;
    uint8_t sc_at_t;
    uint8_t sc_at_start_t;
    uint8_t sc_at_end_t;
    uint32_t t_min;
    uint32_t t_max;
} opentrickletimers_vars_t;

//=========================== prototypes ======================================

void opentrickletimers_init(void);
opentimers_id_t opentrickletimers_create(uint8_t timer_id, uint8_t task_prio);
bool opentrickletimers_initialize(opentimers_id_t id,
                                  uint32_t Imin,
                                  uint8_t Imax,
                                  uint8_t K,
                                  opentimers_cbt cb);
void opentrickletimers_start(opentimers_id_t id);
bool opentrickletimers_stop(opentimers_id_t id);
bool opentrickletimers_recvConsistent(opentimers_id_t id);
bool opentrickletimers_reset(opentimers_id_t id);
uint32_t opentrickletimers_getValue(uint8_t code);

/**
\}
\}
*/

#endif