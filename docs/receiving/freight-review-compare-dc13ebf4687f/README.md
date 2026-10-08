# Freight saved-review comparison receiving packet

This packet accompanies [workflow-checks #50](https://github.com/Jacob-Met/workflow-checks/issues/50). It preserves the source and authored receiving evidence for a standalone consumer of two retained per-load saved-review ZIPs. The report shows full native records, duplicate multiplicities, both saved review histories and exact source identities. A and B retain the caller's supplied order. The comparison makes no claim about current approval or which copy is newer.

## Product entry

From the repository's `freight_packets` directory:

```sh
python -m freightpkt.review_compare COPY_A.zip COPY_B.zip --out comparison.html
python -m unittest discover -s tests -p 'test_review_compare.py' -v
```

Supply two saved review copies for the same load. The consumer validates both complete inputs and renders the report before exclusively creating the selected output. An existing destination is refused. A later write failure may retain a partial new file; publication is not atomic. The [product guide](../../../freight_packets/REVIEW_COMPARE.md) defines the exact accepted format and failure contract.

## Source custody

The product was qualified against main `125339ec63eeb7c4989c9b240c01202555dce573`. Receiving main `76e6175d91320ac816cee019df969c0f0e1bbfc7`, tree `256483cd5c7cbb3731e5a6c322a117900ab24b65`, retains the exact producer `bdcb63507b57d07eed1a6598d7d37d5f5d9db802`, package initializer `a7804a1379966afd1e6143a92cf08c1b25f7abfe` and CI entry `d72b89ae3efb2963fbe7386021f467e82a8e1f2e`. The three new product paths remain absent.

The shared README changed to blob `249ee104175f1d36cc5b39abad5be02bc53e85be`. This assembly preserves all of those current bytes and appends only the already accepted 703-byte comparison section. The runtime, new regression and product guide retain their frozen author identities. Original source and README receipts under `author/` remain historical evidence; they are not rewritten to describe the later README composition.

## Receiving evidence

- [Author receipt](author/AUTHOR-RECEIPT.json): nine pure methods and three separate actual-filesystem methods passed in normal and optimized Python. The earlier zero-space and modeled-I/O records retain their original scope.
- [Actual module receipt](author/qualification/stock-module-receipt.json) and [authored output](author/qualification/comparison.html): the real standalone module ran once from an unrelated working directory and preserved its source and input identities.
- [Independent review](independent/REVIEW.md) and [independent receipt](independent/receiving/receipt.json): 497 checks across seven independently authored native-producer contrasts and six refusals. The reviewer separately read back the author's actual-file receipt; its own actual-file gate refused at zero free space.
- [Copy manifest](COPY-MANIFEST.json): exact product, evidence and carrier correspondence, including the additive README composition.

No GUI, keyboard, layout or actual print receiving is claimed. All compared load data are authored fixtures. No App, real Freight data, account, provider, review action, generation action or payment action was exercised by the consumer's qualification.

The evidence programs retain their original explicit local setups and source locators. They are inert `.source` archives and are not presented as an automatically portable test suite. Original before evidence, corrected reviewer expectations and failed packaging attempts are retained and labelled. The product commands above are the repository entry points. Repository CI remains a receiving gate and is not asserted complete by this assembly.

The author metadata was frozen before its later, explicitly authorized immutable-blob transfer. This later assembly records that transport without changing the original evidence. No compressed transport carrier is duplicated here after its exact logical files have been expanded.
