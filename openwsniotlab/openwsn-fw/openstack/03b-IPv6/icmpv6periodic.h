#ifndef OPENWSN_ICMPv6PERIODIC_H
#define OPENWSN_ICMPv6PERIODIC_H

#include "config.h"
#include "opentimers.h"

#define app_pkPeriodSec 10
#define app_pkLength 20
#define PERIODIC_PORTION 0.5

BEGIN_PACK
typedef struct
{
    uint16_t counter;
    bool is_failed;
    asn_t asn;
} icmpv6periodic_debug_t;
END_PACK

typedef struct
{
    uint16_t counter;
    uint16_t mote_id;
    uint32_t mote_duration;
} icmpv6periodic_info_t;

typedef struct
{
    bool busySending;
    bool alreadyRunning;
    opentimers_id_t timer_id;
    icmpv6periodic_info_t info;
} icmpv6periodic_vars_t;

void icmpv6periodic_init(void);
void icmpv6periodic_sendDone(OpenQueueEntry_t *msg, owerror_t error);
void icmpv6periodic_begin(void);

#endif