#include "config.h"

// #if OPENWSN_ICMPV6PERIODIC_C

#include "opendefs.h"
#include "icmpv6periodic.h"
#include "openqueue.h"
#include "openserial.h"
#include "packetfunctions.h"
#include "idmanager.h"
#include "icmpv6rpl.h"
#include "openrandom.h"
#include "scheduler.h"
#include "opentimers.h"
#include "schedule.h"
#include "neighbors.h"
#include "icmpv6.h"
#include "scheduler.h"
#include "IEEE802154E.h"
#include "board.h"

//=========================== variables =======================================

icmpv6periodic_vars_t icmpv6periodic_vars;

//=========================== prototypes ======================================

void icmpv6periodic_timer_cb(opentimers_id_t id);
owerror_t icmpv6periodic_send(void);

//=========================== public ==========================================

void icmpv6periodic_init(void)
{
    float ms;
    float diff;
    uint16_t myId2B;
    uint32_t rand_num;

    if (idmanager_getIsDAGroot() == TRUE)
    {
        return;
    }

    memset(&icmpv6periodic_vars, 0, sizeof(icmpv6periodic_vars_t));

    myId2B = (idmanager_getMyID(ADDR_64B)->addr_64b[6] << 8) | idmanager_getMyID(ADDR_64B)->addr_64b[7];
    icmpv6periodic_vars.info.mote_id = myId2B;
    icmpv6periodic_vars.info.counter = 0;
    icmpv6periodic_vars.busySending = FALSE;

    ms = app_pkPeriodSec * 1000.0;

    #if PYTHON_BOARD
    ms *= 60;
    #endif

    diff = (float)app_pkPeriodVar * ms;
    icmpv6periodic_vars.min_duration = packetfunctions_mathCeil((ms - diff));
    icmpv6periodic_vars.max_duration = packetfunctions_mathCeil((ms + diff));

    rand_num = openrandom_get16b();
    icmpv6periodic_vars.info.mote_duration = (rand_num % (icmpv6periodic_vars.max_duration - icmpv6periodic_vars.min_duration + 1)) + icmpv6periodic_vars.min_duration;

    icmpv6periodic_vars.timer_id = opentimers_create(TIMER_GENERAL_PURPOSE, TASKPRIO_RPL);
    opentimers_scheduleIn(
        icmpv6periodic_vars.timer_id,
        icmpv6periodic_vars.info.mote_duration,
        TIME_MS,
        TIMER_PERIODIC,
        icmpv6periodic_timer_cb);
}

owerror_t icmpv6periodic_send(void)
{
    OpenQueueEntry_t *msg;
    open_addr_t parentNeighbor;
    bool foundNeighbor;

    if (idmanager_getIsDAGroot() == TRUE)
    {
        opentimers_destroy(icmpv6periodic_vars.timer_id);
        return E_FAIL;
    }

    if (icmpv6periodic_vars.busySending == TRUE)
    {
        return E_FAIL;
    }
    if (ieee154e_isSynch() == FALSE)
    {
        icmpv6periodic_vars.busySending = FALSE;
        return E_FAIL;
    }

    if (icmpv6rpl_getMyDAGrank() == DEFAULTDAGRANK)
    {
        icmpv6periodic_vars.busySending = FALSE;
        return E_FAIL;
    }

    foundNeighbor = icmpv6rpl_getPreferredParentEui64(&parentNeighbor);
    if (foundNeighbor == FALSE) {
        icmpv6periodic_vars.busySending = FALSE;
        return E_FAIL;
    }

    if (schedule_hasNegotiatedCellToNeighbor(&parentNeighbor, CELLTYPE_TX) == FALSE) {
        icmpv6periodic_vars.busySending = FALSE;
        return E_FAIL;
    }

    msg = openqueue_getFreePacketBuffer(COMPONENT_ICMPv6PERIODIC);
    if (msg == NULL)
    {
        icmpv6periodic_vars.busySending = FALSE;
        LOG_ERROR(COMPONENT_ICMPv6PERIODIC, ERR_NO_FREE_PACKET_BUFFER,
                  (errorparameter_t)0,
                  (errorparameter_t)0);
        return E_FAIL;
    }

    // take ownership
    msg->creator = COMPONENT_ICMPv6PERIODIC;
    msg->owner = COMPONENT_ICMPv6PERIODIC;

    // set transport information
    msg->l4_protocol = IANA_ICMPv6;
    msg->l4_sourcePortORicmpv6Type = IANA_ICMPv6_PERIODIC;

    msg->l3_destinationAdd.type = ADDR_128B;
    if (icmpv6rpl_getRPLDODAGid(&msg->l3_destinationAdd.addr_128b[0]) == E_FAIL) {
        icmpv6periodic_vars.busySending = FALSE;
        return E_FAIL;
    }

    // info
    if (packetfunctions_reserveHeader(&msg, sizeof(icmpv6periodic_info_t)) == E_FAIL) {
        icmpv6periodic_vars.busySending = FALSE;
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }

    icmpv6periodic_vars.info.counter += 1;

    memcpy(
        ((icmpv6periodic_info_t*)(msg->payload)),
        &(icmpv6periodic_vars.info),
        sizeof(icmpv6periodic_info_t)
    );

    // payload (zero)
    uint8_t size = app_pkLength-(msg->length+sizeof(ICMPv6_ht)+10);
    if (packetfunctions_reserveHeader(&msg, size) == E_FAIL) {
        icmpv6periodic_vars.busySending = FALSE;
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }
    memset(&msg->payload[0], 0, size);

    if (packetfunctions_reserveHeader(&msg, sizeof(ICMPv6_ht)) == E_FAIL) {
        openqueue_freePacketBuffer(msg);
        return E_FAIL;
    }

    ((ICMPv6_ht *) (msg->payload))->type = msg->l4_sourcePortORicmpv6Type;
    ((ICMPv6_ht *) (msg->payload))->code = 0;
    packetfunctions_calculateChecksum(msg, (uint8_t * ) & (((ICMPv6_ht *) (msg->payload))->checksum));//do last

    bool result = icmpv6_send(msg);
    LOG_INFO(COMPONENT_ICMPv6PERIODIC, ERR_PERIODIC_SEND, icmpv6periodic_vars.info.counter, result);

    if (result == E_SUCCESS)
    {
        icmpv6periodic_vars.busySending = TRUE;
        return E_SUCCESS;
    }
    else
    {
        openqueue_freePacketBuffer(msg);
        icmpv6periodic_vars.busySending = FALSE;
        return E_FAIL;
    }
}

void icmpv6periodic_sendDone(OpenQueueEntry_t *msg, owerror_t error) {
    msg->owner = COMPONENT_ICMPv6PERIODIC;
    if (msg->creator != COMPONENT_ICMPv6PERIODIC) {//that was a packet I had not created
        LOG_ERROR(COMPONENT_ICMPv6PERIODIC, ERR_UNEXPECTED_SENDDONE, (errorparameter_t) 0, (errorparameter_t) 0);
    }
    openqueue_freePacketBuffer(msg);
    icmpv6periodic_vars.busySending = FALSE;
}

void icmpv6periodic_timer_cb(opentimers_id_t id)
{
    if (idmanager_getIsDAGroot() == TRUE)
    {
        return;
    }

    icmpv6periodic_send();
}

// #endif /* OPENWSN_ICMPV6PERIODIC_C */
