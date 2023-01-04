// Copyright 2022 Northern.tech AS
//
//	Licensed under the Apache License, Version 2.0 (the "License");
//	you may not use this file except in compliance with the License.
//	You may obtain a copy of the License at
//
//	    http://www.apache.org/licenses/LICENSE-2.0
//
//	Unless required by applicable law or agreed to in writing, software
//	distributed under the License is distributed on an "AS IS" BASIS,
//	WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//	See the License for the specific language governing permissions and
//	limitations under the License.

package deployments

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/pkg/errors"

	"github.com/mendersoftware/go-lib-micro/log"

	"github.com/mendersoftware/reporting/utils"
)

const (
	urlDeviceDeployments = "/api/internal/v1/deployments/tenants/:tid/deployments/devices/:id"
	defaultTimeout       = 10 * time.Second
)

//go:generate ../../x/mockgen.sh
type Client interface {
	// GetLatestDeployment retrieves the latest deployment for a given device
	GetLatestFinishedDeployment(
		ctx context.Context,
		tenantID string,
		deviceID string,
	) (*DeviceDeployment, error)
}

type client struct {
	client  *http.Client
	urlBase string
}

func NewClient(urlBase string) Client {
	return &client{
		client:  &http.Client{},
		urlBase: urlBase,
	}
}

func (c *client) GetLatestFinishedDeployment(
	ctx context.Context,
	tenantID string,
	deviceID string,
) (*DeviceDeployment, error) {
	l := log.FromContext(ctx)

	url := utils.JoinURL(c.urlBase, urlDeviceDeployments)
	url = strings.Replace(url, ":tid", tenantID, 1)
	url = strings.Replace(url, ":id", deviceID, 1)

	ctx, cancel := context.WithTimeout(ctx, defaultTimeout)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, errors.Wrapf(err, "failed to create request")
	}

	q := req.URL.Query()
	q.Add("page", "1")
	q.Add("per_page", "1")
	req.URL.RawQuery = q.Encode()

	rsp, err := c.client.Do(req)
	if err != nil {
		return nil, errors.Wrapf(err, "failed to submit %s %s", req.Method, req.URL)
	}
	defer rsp.Body.Close()

	if rsp.StatusCode == http.StatusNotFound {
		return nil, nil
	} else if rsp.StatusCode != http.StatusOK {
		err := errors.Errorf("%s %s request failed with status %v",
			req.Method, req.URL, rsp.Status)
		l.Errorf(err.Error())
		return nil, err
	}

	dec := json.NewDecoder(rsp.Body)
	var devDevs []*DeviceDeployment
	if err = dec.Decode(&devDevs); err != nil {
		return nil, errors.Wrap(err, "failed to parse request body")
	} else if len(devDevs) == 0 {
		return nil, nil
	}
	return devDevs[0], nil
}