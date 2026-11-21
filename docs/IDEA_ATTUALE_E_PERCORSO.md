# Team Bari: current project idea and decision path

**Comparison document for the team - November 13, 2026**

**Note of 20 November 2026.** This document retains the decisions of the first revisions. The
current code focuses on the verification of the capture and derivation of the final file. See the
[README](../README.md).

**Update of 14 November 2026:** the didactic CROSS backend described in this document has been
replaced by the official reference C library v2.2. Receiveds have been added signed by the
coordinator, which keeps its private key separate from those of the participants. The current suite
includes 36 tests, with official CROSS test vectors; the regeneration of 100 KAT of each small/fast
variant coincides with the SHA-512 upstream. For updated status, installation and limits see the
[Main README](../README.md). The rest of the document retains the decision path of the first
revision. The old toolkit HQC/MPC/ZKP/XRPL and its regressions have been removed from the repository
because they are not used by the current protocol. References to those files in the following
sections describe the previous work. The deadline now uses time receipts signed by validators,
separated from approvals, with unchangeable threshold and tolerance. The coordinator's watch does
not decide the admission; evidence produced before the deadline can be delivered later. `SCADUTO` is replaced by
`IN_ATTESA_DI_PROVE` when a quorum observes the term: a final closure still requires proof of
completeness. No integration has been introduced XRPL.

This document describes the agreed direction and the first implementation. The track of the
hackathon 2026 is not yet available: we prepare a reusable base, without assuming that the challenge
will necessarily be an election or a game.

## 1. The idea in a nutshell

We want a protocol in which users can record a pseudonymous identifier and publish contributions in
the form of a commitment. A set of authorized validators controls contributions and signs their
results. A contribution is accepted when it reaches the threshold set for the session.

**Registering allows you to send requests, but does not automatically attribute validation power,
tokens or voting rights.**

The server coordinates the process: it opens the session, displays the configuration, collects the
contributions and checks the attestations. In the current version the server is centralized; the
next goal is to have the checks performed at distinct nodes. We do not describe the prototype as a
network already decentralized or trustless.

## 2. From where we started

### Project Experience 2025

Last year the Team Bari won third place with ZK-F1-AI. The project used commitment of the state of
the cars, ZK tests on operations and a commit-reveal mechanism, with contracts on Ethereum.

The lesson to be taken is the connection between state, operations allowed and result: each
encryption component must solve a problem of the protocol. A collection of algorithms alone does not
constitute a complete solution.

By examining the code stored in the Hardhat artifacts we also clarified the theme of multiple
accounts: there were controls for address and commitment, but not a verification of the uniqueness
of the person. The tokens were initially assigned to the deployer and distributed in the test
script, not automatically given to each new wallet. This handled the setup of the demo, without
generally solving the problem of a person who controls multiple accounts.

### The toolkit prepared for 2026

The initial repository collected HQC, CROSS, commitment on syndrome, range testing, Shamir and XRPL
anchoring tools. The old `versione_facile` added dynamic recordings, identity files and signature
collection.

The revision showed that the flow did not yet realize the guarantees described. In particular, the
server knew the secret and generated the private keys of users. In the easy version were also
reproduced:

- recovery of secret from a single quota using the public seed of the polynomial;
- Decryption of simplified KEM using public information;
- forgery of a simplified signature;
- achievement of quorum by adding signatures on different proposals.

These findings concern those implementations: they are not attacks on the official HQC or CROSS
algorithms. They motivated the elimination of the old six scripts of the easy version and the
construction of a new session stream. The rest of the toolkit remains study material, with limits to
be evaluated separately.

## 3. What we've got from previous tracks

| Edition | Central problem | Indication for us |
| --- | --- | --- |
| 2024: De Cifris election | The president may alter the result or omit local scrutins. The local count is taken correct. | You need completeness of contributions and correctness of aggregation. |
| 2025: F1-AI | Car status and formula must remain secret; training and races must respect the rules even with dishonest players or servers. | We need secret management, accepted transitions and verification of the result. |

In 2025 the parameters must be unknown to the owner as well and the changes must be random. A test
of the change interval only does not show randomness; a signature does not show the correctness of
the speed. The challenge also does not establish that the secret formula is linear.

Both tracks require a blockchain, but do not impose a particular post-quantum algorithm in the
slides. The project will first solve the application problem of the new track.

Original sources, linked by [Official page IXH26](https://www.decifris.it/ixh26/):

- [Track IXH24, Track 1](https://drive.google.com/file/d/17NaxyjnmY-VAdZkmY0pDQbstzSYeB6LZ/view).
- [Track IXH25, Track 1](https://drive.google.com/file/d/1NkwMQN705u5xdYd7kk1a06ZXsT0FkGtH/view).

## 4. The three roles of the current architecture

| Role | What Can You Do | What power doesn't automatically receive |
| --- | --- | --- |
| Registered user | Publish signed contributions with your key. | He doesn't become a validator and he doesn't get an electoral right. |
| Authorized validator | Check a contribution and sign a positive or negative outcome. | It cannot change thresholds, committees or contributions on its own. |
| Coordinator Server | Configure a new session and collect requests and attestations. | His statements alone do not replace the signatures of the validators. |

Anyone with the public data can check the signatures. Only validators listed in the session
configuration are included in the quorum.

There remains an explicit trust in the coordinator for the initial configuration, data availability,
completeness of what it shows and the clock. The current implementation does not eliminate these
responsibilities.

## 5. The agreed flow

### A. Opening of the session

The coordinator shall establish and make available:

- System and session identifier;
- list of validators' public keys;
- number of approvals required;
- maturity;
- Application rule identifier to be checked.

Configuration has a cryptic imprint. The signatures of the session are linked to that fingerprint,
which also includes the signature suite.

**List, threshold and expiration do not change during the session.** A new configuration requires a
new session; we have not introduced a dynamic update protocol for validators.

### B. pseudonym registration

The client generates the CROSS keys and keeps the private one. The server sends a random challenge
for single use; the client signs it and shows to check the key that it wants to register. The
request is also linked to the session configuration.

The user log contains a pseudonym and a public key identifier. It does not require a private name,
surname or key. The same key does not register twice in the session.

This is pseudonymized: messages from the same key can be connected. We do not promise network
anonymity, impossibility of indirect identification or a permanent log between sessions, which is
not yet implemented.

### C. Publication of the contribution

The user signs a message that binds together author, commitment, digest of any application test,
nonce and session configuration. The nonce distinguishes requests and cannot be reused by the same
author in the same session.

The coordinator shall check the registration, signature and application rule before admitting the
contribution to the collection of the attestations.

### D. Verification of validators

Each node must independently verify the contribution according to the same rule and sign an outcome
related to the specific contribution and configuration.

A valid signature responds to who has authorized this
message?.................................................................................................................................................................................................................................................................................................................................................................................................................................

### E. Decision and deadline

The coordinator only accepts signatures of the configured validators. Each validator counts once per
contribution; different contributions or sessions do not add up. A key cannot be listed under two
names to count twice.

| State | Condition |
| --- | --- |
| `IN_ATTESA` | There are not enough approvals yet, but the threshold remains reachable. |
| `APPROVATO` | The threshold was reached before the deadline. |
| `RIFIUTATO` | Negative attestations make it impossible to reach it. |
| `SCADUTO` | The deadline comes without a final decision. |

At the end of the period, the threshold does not fall, and an absence is not transformed into an
approval, and the final decisions remain the same.

## 6. Example: five validators, four approvals

The server opens S1 with five validators and threshold four. Alice registers without publishing her
name and sends a signed commitment.

1. Three validators approve: the contribution remains pending.
2. Here comes the fourth valid approval: it becomes approved.
3. A second contribution receives only three approvals before the deadline:
   It gets expired, without lowering the threshold.
4. If Alice creates a hundred new accounts, no one automatically enters the committee.
   Those accounts can't build a quorum in their favor.

With threshold four out of five, a single negative outcome is not enough to permanently block the
contribution; two negative outcomes make four approvals impossible. Four out of five is a
demonstration configuration, not a universal security formula. Counting signatures does not amount
to implementing BFT consent.

## 7. Ideas discarded or postponed

| Idea discussed | Current decision | Reason |
| --- | --- | --- |
| All subscribers become validators with the same weight. | Rejected. | A person could create many accounts and check the quorum. |
| Each contribution requires unanimity. | Discarded for this first version. | A single node absent or hostile could block everything. |
| Random threshold, possibly with post-quantum generator. | Rejected. | Randomness can produce an insufficient threshold and does not define a security model. |
| Threshold updated periodically based on online users. | Rejected. | Users are not validators; inputs and disconnects must not change the conditions at the start of the process. |
| Updating of the committee during a session with approvals of the previous configuration. | Recommended. | Introduces unnecessary complexity to the first objective. |
| A person can register only once, always. | Deferred until the challenge is known. | Keys and IPs do not demonstrate personal uniqueness; a licensing procedure is needed if the right is personal. |
| The server generates private keys, secrets and shares for everyone. | Removed from the new flow. | It does not achieve the objective of separating the coordinator from the secrets of users. |
| Three signature backends: CROSS, UOV and SNOVA. | Resized and postponed. | First we need a complete protocol. UOV remains a possible comparison related to the thesis work; NOVA a subsequent reference. |
| A generic ZKP solves registration and legitimacy. | Discarded as a setting. | The property to be proved and the procedure for assigning the right must be specified. |

### The distinction between accounts and rights

The comparison with Bitcoin helped us to formulate the problem better: being able to create many
keys should not mean being able to create power arbitrarily. We are not copying Bitcoin's consensus,
nor implementing proof-of-work.

For now we guarantee a key registration in the session, not one per person. If the track will
require a vote per person

## 8. Why CROSS and what role can OVU play

CROSS has been chosen to authenticate requests and attestations. It is a signature derived from
zero-knowledge evidence, but its internal evidence does not replace an application test on the vote,
commitment or uniqueness of the person.

UOV and SNOVA were discussed for the thesis work of a team member. The modularity of the signature
may be useful as a demonstration comparison, but it is not the main contribution of the project.
They are not currently integrated.

The discussion on Craig Gidney's article also made it clear that adding post-quantum signatures to
application messages does not automatically post-quantum the blockchain below. Verifiers and links
between signed objects must also be corrected: two signatures do not correct a wrong rule.

References: [CROSS](https://www.cross-crypto.com/), [VOW](https://www.uovsig.org/homepage),
[discussed article](https://algassert.com/post/2602).

## 9. What exists today and what is missing

| Component | Current status |
| --- | --- |
| Unchangeable session configuration | Implemented. |
| Registration with single-use challenge and signature | Implemented in memory, per session. |
| Public register of aliases and keys | It can be consulted via Python API; it is not yet a public service on the network. |
| Separating between users and validators | Implemented. |
| Contributions and attestations related to the same configuration | Implement. |
| Fixed Quorum, Duplicates, Waste and Expires | Implement. |
| Application control of hidden content | Explicit interface; only a 32-byte commitment occurs in the demo without trial. |
| Official CROSS with compliant parameters | To be integrated: you still use the customized CROSS didactic toolkit. |
| Persistence and restoration | To be implemented. A reboot loses the status and replay controls already consumed. |
| Communication and synchronization between distinct nodes | To be implemented; the demo simulates them in the same process. |
| Personal identity, voting eligibility and vote not linked to the account | Not implemented. To be evaluated according to the track. |
| XRPL transactions confirmed and verified by ledger | To be integrated. Preexisting study tools are not the new on-chain flow. |
| Final calculation, completeness of inputs and management of secrets | To be defined and implemented on the case of use. |

25 tests have passed: 15 on the new session scenarios and 10 regressions of the previous toolkit.
They are behavior checks, not a general security proof or an audit of the primitive.

The current material is in `protocollo/sessione.py`, `versione_facile/demo_sessione.py` and
`tests/test_sessione.py`. Previous flow documents and changelogs remain historical and also describe
components that have been removed. Runtime files of old identities have not been deleted and are not
used by the new demo.

## 10. How to show it and what to build after

From the root of the repository:

```bash
python3 -B versione_facile/demo_sessione.py
python3 -B -m unittest discover -s tests -v
```

The demo shows pseudonym recording, self-promotion attempt at validator, approval with four
signatures and expiration with three signatures. Keys are generated by simulated clients and are not
printed.

The proposed work order is:

1. **Persistence:** save configuration, recordings, contributions, nonce and
   attestations, with consistent restoration after a restart.
2. **Consistent signature backend:** replace the didactic CROSS and check it
   integration with appropriate test vectors.
3. **Differing nodes:** carry messages and have each node verify the
   same data, facing availability and possible discordant views.
4. **S track rules:** set rights, application controls, possible
   distributed secrets and result calculation function.
5. **Role of XRPL:** Integrate the public register where it adds a guarantee
   concrete, verifying transactions and confirmed data.

The message to share in the team is: **We are building a protocol of signed and verified
contributions with fixed committee and quorum per session.** The management of people, the meaning
of the contribution and the result to be certified will be specialized on the track.The priority is
to make the flow consistent and verifiable, before adding other primitive or demo options.
