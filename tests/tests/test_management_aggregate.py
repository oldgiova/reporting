# Copyright 2022 Northern.tech AS
#
#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import pytest
import re
import time

from typing import Union

import internal_api
import management_api
import utils


class TestManagementSearch:
    @pytest.fixture(scope="class", autouse=True)
    def setup_test_context(self, opensearch):
        # clean up any indices from previous tests
        indices = opensearch.cat.indices(format="json")
        for idx in indices:
            if not idx["index"].startswith("."):
                opensearch.delete_by_query(
                    index=[idx["index"]], body={"query": {"match_all": {}}}
                )

        for dev in self._test_set:
            utils.index_device(dev)

        time.sleep(5)

    class _TestCase:
        def __init__(
            self,
            aggregation_terms: management_api.models.AggregationTerms,
            http_code: int,
            result: Union[list[management_api.models.Aggregation], str],
            authorization: str = None,
        ):
            self.aggregation_terms = aggregation_terms
            self.http_code = http_code
            self.result = result
            self.authorization = authorization

    _test_set = [
        internal_api.models.InternalDevice(
            id="463e12dd-1adb-4f62-965e-b0a9ba2c93ff",
            tenant_id="123456789012345678901234",
            name="bagelBone",
            attributes=[
                management_api.models.Attribute(
                    name="string", value="Lorem ipsum dolor sit amet", scope="inventory"
                ),
                management_api.models.Attribute(
                    name="number", value=2 ** 47, scope="inventory"
                ),
            ],
        ),
        internal_api.models.InternalDevice(
            id="d8b04e01-690d-41ce-8c6d-ab079a04d488",
            tenant_id="123456789012345678901234",
            name="blueberryPi",
            attributes=[
                management_api.models.Attribute(
                    name="string",
                    value="consectetur adipiscing elit",
                    scope="inventory",
                ),
                management_api.models.Attribute(
                    name="number", value=420.69, scope="inventory"
                ),
            ],
        ),
        internal_api.models.InternalDevice(
            id="ad707aab-916b-4ec9-a43f-0031b2bcf9ad",
            tenant_id="123456789012345678901234",
            name="birch32",
            attributes=[
                management_api.models.Attribute(
                    name="string", value="sed do eiusmod tempor", scope="inventory",
                ),
            ],
        ),
        internal_api.models.InternalDevice(
            id="85388603-5852-437f-89c4-7549502893d5",
            tenant_id="123456789012345678901234",
            name="birch32",
            attributes=[
                management_api.models.Attribute(
                    name="string", value="incididunt ut labore", scope="inventory",
                ),
                management_api.models.Attribute(
                    name="number", value=0.0, scope="inventory"
                ),
            ],
        ),
        internal_api.models.InternalDevice(
            id="98efdb94-26c2-42eb-828d-12a5d6eb698c",
            tenant_id="098765432109876543210987",
            name="shepherdsPi",
            attributes=[
                management_api.models.Attribute(
                    name="string", value="sample text", scope="inventory",
                ),
                management_api.models.Attribute(
                    name="number", value=1234, scope="inventory"
                ),
            ],
        ),
    ]

    @pytest.mark.parametrize(
        argnames="test_case",
        argvalues=[
            _TestCase(
                authorization=utils.generate_jwt(tenant_id="123456789012345678901234"),
                aggregation_terms=management_api.models.AggregationTerms(
                    filters=[
                        management_api.models.FilterTerm(
                            attribute="string",
                            value="Lorem ipsum dolor sit amet",
                            type="$ne",
                            scope="inventory",
                        )
                    ],
                    aggregations=[
                        management_api.models.AggregationTerm(
                            name="string",
                            attribute="string",
                            scope="inventory",
                            limit=10,
                        )
                    ],
                ),
                http_code=200,
                result=[
                    management_api.models.Aggregation(
                        name="string",
                        other_count=0,
                        items=[
                            management_api.models.AggregationItem(
                                key="consectetur adipiscing elit", count=1,
                            ),
                            management_api.models.AggregationItem(
                                key="incididunt ut labore", count=1,
                            ),
                            management_api.models.AggregationItem(
                                key="sed do eiusmod tempor", count=1,
                            ),
                        ],
                    ),
                ],
            ),
            _TestCase(
                authorization=utils.generate_jwt(tenant_id="anIllegalTenantID"),
                aggregation_terms=management_api.models.AggregationTerms(
                    aggregations=[
                        management_api.models.AggregationTerm(
                            name="string",
                            attribute="string",
                            scope="inventory",
                            limit=10,
                        )
                    ],
                ),
                http_code=200,
                result=[],
            ),
            _TestCase(
                aggregation_terms=management_api.models.AggregationTerms(
                    aggregations=[
                        management_api.models.AggregationTerm(
                            name="string",
                            attribute="string",
                            scope="inventory",
                            limit=10,
                        )
                    ],
                ),
                http_code=401,
                result=[],
            ),
        ],
        ids=["ok", "error, missing index for tenant", "error, unauthorized access",],
    )
    def test_search(self, test_case, setup_test_context):
        conf = None
        if test_case.authorization is not None:
            conf = management_api.Configuration.get_default_copy()
            conf.access_token = test_case.authorization
        api_client = management_api.ApiClient(configuration=conf)
        client = management_api.ManagementAPIClient(api_client=api_client)
        try:
            body, status, headers = client.aggregate_with_http_info(
                aggregation_terms=test_case.aggregation_terms
            )
        except management_api.ApiException as r:
            body = r.body
            status = r.status
            headers = r.headers
        assert status == test_case.http_code
        if isinstance(test_case.result, str):
            assert isinstance(body, bytes)
            re.match(test_case.result, r.body.decode())
        elif len(test_case.result) > 0:
            assert isinstance(body, type(test_case.result))

            expected = [dev.name for dev in test_case.result]
            actual = [dev.name for dev in body]
            assert actual == expected

            for i, expected in enumerate(test_case.result):
                actual = body[i]
                for attr in expected.items:
                    assert attr in actual.items