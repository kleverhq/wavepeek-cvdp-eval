# syntax=docker/dockerfile:1

ARG CVDP_SIM_IMAGE=nvidia/cvdp-sim:v1.0.0

FROM node@sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94 AS node_tools
ARG PI_NPM_INTEGRITY
ARG PI_GIT_COMMIT
RUN test "$(npm view @earendil-works/pi-coding-agent@0.83.0 dist.integrity)" = "$PI_NPM_INTEGRITY" \
    && test "$(npm view @earendil-works/pi-coding-agent@0.83.0 gitHead)" = "$PI_GIT_COMMIT" \
    && npm install --global --ignore-scripts @earendil-works/pi-coding-agent@0.83.0

FROM rust@sha256:d0a4aa3ca2e1088ac0c81690914a0d810f2eee188197034edf366ed010a2b382 AS treatment_builder
COPY agent/.build/treatment-source.tar /tmp/source.tar
RUN mkdir /src && tar -xf /tmp/source.tar -C /src \
    && cd /src \
    && cargo build --release --locked \
    && mkdir -p /out/docs \
    && cp target/release/wavepeek /out/wavepeek \
    && /out/wavepeek skill > /out/SKILL.md \
    && /out/wavepeek docs export /out/docs

FROM ${CVDP_SIM_IMAGE} AS common
ARG PI_SUBAGENTS_SHA
ARG PI_SUBAGENTS_SOURCE_SHA256
COPY --from=node_tools /usr/local/ /usr/local/
COPY agent/.build/pi-subagents-source.tar /tmp/pi-subagents-source.tar
COPY agent/patch-pi-subagents.py /opt/cvdp-pi/patch-pi-subagents.py
COPY agent/common/general-purpose.md /opt/cvdp-pi/general-purpose.md
COPY config/pi/ /opt/cvdp-pi/config/pi/
RUN mkdir -p /opt/pi-subagents \
    && tar -xf /tmp/pi-subagents-source.tar -C /opt/pi-subagents \
    && cd /opt/pi-subagents \
    && npm ci --omit=dev --omit=peer --ignore-scripts \
    && test ! -e node_modules/@earendil-works/pi-coding-agent \
    && python3 /opt/cvdp-pi/patch-pi-subagents.py \
    && rm /tmp/pi-subagents-source.tar \
    && chmod -R a+rX /opt/cvdp-pi /opt/pi-subagents
ENTRYPOINT []
CMD ["/bin/sh"]
LABEL org.cvdp-pi.pi.version="0.83.0" \
      org.cvdp-pi.pi-subagents.commit="${PI_SUBAGENTS_SHA}" \
      org.cvdp-pi.pi-subagents.source-sha256="${PI_SUBAGENTS_SOURCE_SHA256}"

FROM common AS baseline
LABEL org.cvdp-pi.arm="baseline"

FROM common AS wavepeek
ARG WAVEPEEK_SHA
ARG WAVEPEEK_SOURCE_SHA256
COPY --from=treatment_builder /out/wavepeek /opt/wavepeek/bin/wavepeek.real
COPY --from=treatment_builder /out/SKILL.md /opt/wavepeek/skills/wavepeek/SKILL.md
COPY --from=treatment_builder /out/docs/ /opt/wavepeek/docs/
COPY agent/wavepeek-wrapper.py /usr/local/bin/wavepeek
RUN chmod 0755 /usr/local/bin/wavepeek /opt/wavepeek/bin/wavepeek.real \
    && chmod -R a+rX /opt/wavepeek
LABEL org.cvdp-pi.arm="wavepeek" \
      org.wavepeek.commit="${WAVEPEEK_SHA}" \
      org.wavepeek.source-sha256="${WAVEPEEK_SOURCE_SHA256}"
