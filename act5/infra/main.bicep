// Act 5: a real Durable Task Scheduler in Azure. The worker stays on the laptop.
//
// That split is the whole demo: Acts 1-3 run against the emulator in Docker, Act 5 runs the *same*
// `make act2` against a scheduler in Sweden Central. The kill still lands on a local process, and the
// state it was holding is provably not on this machine — the portal shows it while the worker is dead.
//
// Deliberately small: one resource group, two resources, one role assignment. `azd down` removes it.

targetScope = 'subscription'

@minLength(1)
@description('Name of the azd environment; seeds the resource names.')
param environmentName string

@minLength(1)
@description('Region. Must support Durable Task Scheduler.')
param location string

@description('Object id of the identity that runs the worker (the signed-in user).')
param principalId string

@allowed(['Consumption', 'Dedicated'])
@description('Consumption is pay-per-action and right for a demo.')
param schedulerSku string = 'Consumption'

var tags = { 'azd-env-name': environmentName, project: 'ntk2026-kill-your-agent', act: '5' }

resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: tags
}

module resources 'resources.bicep' = {
  name: 'act5-scheduler'
  scope: rg
  params: {
    location: location
    tags: tags
    token: uniqueString(subscription().id, environmentName, location)
    principalId: principalId
    schedulerSku: schedulerSku
  }
}

output AZURE_LOCATION string = location
output AZURE_RESOURCE_GROUP string = rg.name
output DTS_ENDPOINT string = resources.outputs.schedulerEndpoint
output DTS_TASKHUB string = resources.outputs.taskHubName
output DTS_TENANT string = subscription().tenantId
output DTS_DASHBOARD string = resources.outputs.dashboardUrl
