## LIST of packet tx + ack rx for a specific SRC


SELECT pkt.asn, pkt.src, pkt.dest, pkt2.src AS srcack
FROM pkt, pkt as pkt2
WHERE pkt.asn = pkt2.asn AND pkt.type='DATA' AND pkt.event='TX' AND pkt2.type='ACK' AND pkt2.event='RX' AND pkt.src='141592cc00000003'



## list of data tx from 03 where no ack is received
SELECT *
FROM pkt P
LEFT JOIN pkt P2
ON P.asn = P2.asn
AND P.event='TX' 
AND P.type='DATA' 
AND P2.event='TX'
AND P2.type='ACK'
WHERE P.event='TX' AND P.type='DATA' AND P.src='141592cc00000003' AND P2.src IS NULL  AND P.dest!='ffffffffffffffff'



## count the nb of unacked packets per source, per cell
SELECT COUNT(P.src), P.src, P.dest, P.slotOffset, *
FROM pkt P
LEFT JOIN pkt P2
ON P.asn = P2.asn
AND P.event='TX' 
AND P.type='DATA' 
AND P2.event='TX'
AND P2.type='ACK'
WHERE P.event='TX' AND P.type='DATA' AND P2.src IS NULL  AND P.dest!='ffffffffffffffff'
GROUP BY P.src, P.slotOffset