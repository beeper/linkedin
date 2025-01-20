package connector

import (
	_ "embed"
	"strings"
	"text/template"

	up "go.mau.fi/util/configupgrade"
	"gopkg.in/yaml.v3"
)

//go:embed example-config.yaml
var ExampleConfig string

type Config struct {
	DisplaynameTemplate string             `yaml:"displayname_template"`
	displaynameTemplate *template.Template `yaml:"-"`
}

type umConfig Config

func (c *Config) UnmarshalYAML(node *yaml.Node) error {
	err := node.Decode((*umConfig)(c))
	if err != nil {
		return err
	}

	c.displaynameTemplate, err = template.New("displayname").Parse(c.DisplaynameTemplate)
	return err
}

func upgradeConfig(helper up.Helper) {
	helper.Copy(up.Str, "displayname_template")
}

type DisplaynameParams struct {
	FirstName string
	LastName  string
}

func (c *Config) FormatDisplayname(firstName, lastName string) string {
	var nameBuf strings.Builder
	err := c.displaynameTemplate.Execute(&nameBuf, &DisplaynameParams{
		FirstName: firstName,
		LastName:  lastName,
	})
	if err != nil {
		panic(err)
	}
	return nameBuf.String()
}

func (lc *LinkedInConnector) GetConfig() (string, any, up.Upgrader) {
	return ExampleConfig, &lc.Config, &up.StructUpgrader{
		SimpleUpgrader: up.SimpleUpgrader(upgradeConfig),
		Base:           ExampleConfig,
	}
}
