# Changelog

### Commit: `a5da55105b7d6f53431adc35f38f85b0d8f7ff26`
* Changed the client `send_seq` to be initialized as `Y`, from `Y+1`
* Changed the server `send_seq` to be initialized as `X+1`, from `X+2`
* Datapackets are sent with `send_seq`, THEN `send_seq` is incremented by 1
  * For example, the first PoopDataPacket (henceforth PDP) sent by the client would have a seq number of `Y`, NOT `Y+1`. Likewise, the first PDP sent by the server would have a seq number of `X+1`, NOT `X+2`
* Changed the hashing to be hashing over the whole packet, but with the default `datahash` field defined as `0`, of type `UINT32`. On a `transport.write()`, the whole PDP is hashed, then that hash is set as the packet's new datahash. This updated packet is serialized and sent over. On the receiving end, the protocol checks this received packet's datahash with a generated datahash created in the same way: the packet's `datahash` field is set to the default value of 0, and this whole packet is hashed. The received datahash is then compared to the generated datahash.
* Added a way for written packets to have a MTU. If the higher layer pushes data where `len(data) > MTU`, the data is broken up into `n` chunks `c1..cn` where `len(ci) <= MTU`. This is then sent as `n` PDPs, with all the sequencing and aforementioned hashing, etc.

### Commit: `d76b10c972bde9ac7b3a1f7c03c90a1ce093d969`
* Added in sending an ack packet where `ack` is set to the received packet's `syn`. For example, if the receiver receives a packet with `syn`=X, it will send back an ack packet with `ack`=X.