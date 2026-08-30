# Hand-marked answers

Realistic model answers, in three languages, with **every** particular marked by
hand. They exist to measure the one number the generated corpus cannot: how much
of an answer nobody wrote for akashi does akashi actually see.

The generated corpus measures the *detector* against known plants. Its prose was
authored for it, so a hundred per cent there says the method works on material
designed for the method. These say something different and harder.

## The marking rule

A particular is marked when **a person reading the sentence would say a wrong
value there changes what it means** — ADR-0004's definition, applied by hand and
not by running the extractor and writing down what it found. That distinction is
the whole point: a marking derived from the implementation measures nothing.

So proper nouns are marked, and akashi extracts none of them. That drags recall
down, honestly, and it is why the score is reported twice: once over every marked
particular, and once over only the kinds akashi claims to cover. The first is
coverage. The second is whether it does what it says.

```markdown
{{P:reference}}第30条{{/P}}により、{{P:quantity}}30日{{/P}}前の書面通知で解約できます。
```

The markup is stripped and the offsets are computed. Nothing is typed.

## What these cannot tell you

Nine answers is a sample, not a distribution. They were written by one model, in
one sitting, about three genres — and the person who marked them is the person
who wrote the extractor, which is the exact bias `docs/adr/0010` warns about for
a labelled corpus. The mitigation is the rule above and the fact that the
markings are visible in the files: anyone can disagree with one.

A larger set drawn from real traffic would be worth more than all of this, and
it is not something a local-first project can collect for itself.
