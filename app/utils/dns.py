import dns.resolver
import dns.name
import dns.rdatatype
import os
import random

from typing import Iterator, NamedTuple


resolver = dns.resolver.Resolver(configure=False)
resolver.nameservers = [os.getenv("DNS_ADDR", "172.31.1.88")]
resolver.search = [
    dns.name.from_text("service.city.consul"),
    dns.name.from_text("service.consul"),
]


class Entry(NamedTuple):
    ip: str
    port: str


class Service:
    def __init__(self, response):
        self.response = response
        self._parse_response()
        self.response_generator = self._response()

    def _parse_response(self) -> None:
        """Parse the DNS response into something a litte more useful.  PyDNS
        object model is too complicated for everyday use."""

        nodes = {}
        for x in self.response.additional:
            if x.rdtype == dns.rdatatype.A:
                nodes[x.name.to_text().strip(".")] = x[0].address

        self.srv = []
        self.weights = []

        max_priority = max([r.priority for r in self.response.answer[0]])

        for record in self.response.answer[0]:
            if record.priority == max_priority:
                self.srv.append(
                    Entry(nodes[record.target.to_text().strip(".")], str(record.port))
                )
                self.weights.append(record.weight)

    def _weighted_choice(self) -> Entry:
        return random.choices(self.srv, self.weights, k=1)[0]

    def _response(self) -> Iterator[Entry]:
        """Returns a Entry tuple of the ip address and the port via weighted
        random choice"""
        while True:
            yield self._weighted_choice()

    @property
    def url(self) -> str:
        entry = next(self.response_generator)
        return f"{entry.ip}:{entry.port}"

    @property
    def ip(self) -> str:
        return next(self.response_generator).ip

    @property
    def port(self) -> str:
        return next(self.response_generator).port

    def entries(self):
        return self.srv


def discover_service(service_name: str) -> Service:
    answer = resolver.query(service_name, "SRV")
    return Service(answer.response)