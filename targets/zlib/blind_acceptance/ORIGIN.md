# Blind acceptance input

The input is enwik8, the published 100,000,000-byte prefix of the English Wikipedia pages-articles dump dated 2006-03-03.

- Zip: `http://mattmahoney.net/dc/enwik8.zip`
- Documentation and published checksums: `http://mattmahoney.net/dc/textdata.html`
- Upstream dump named by that page: `http://download.wikipedia.org/enwiki/20060303/enwiki-20060303-pages-articles.xml.bz2`
- Zip length: 36,445,475 bytes
- Zip SHA-256: `547994d9980ebed1288380d652999f38a14fe291a6247c157c3d33d4932534bc`
- Member: `enwik8`
- Member length: 100,000,000 bytes
- Published MD5: `a1fa5ffddb56f4953e226637dabbb36a`
- Published SHA-1: `57b8363b814821dc9d47aa4d41f58733519076b2`
- Member SHA-256: `2b49720ec4d78c3c9fabaee6e4179a5e997302b3a70029f30f2d582218c024a8`

The published MD5 and SHA-1 were checked against the downloaded zip before this manifest was sealed. The member SHA-256 is the hash of those same bytes. Expected gzip bytes are not stored.

This is not the Canterbury tarball `cantrbry.tar.gz` (`f140e8a5b73d3f53198555a63bfb827889394a42f20825df33c810c3d5e3f8fb`). The license is recorded in `LICENSE.md`. The repository MIT license does not cover `enwik8.zip`.

`MANIFEST.json` is the seal record. `SEAL.sha256` is the SHA-256 of that manifest after CRLF is turned into LF.
