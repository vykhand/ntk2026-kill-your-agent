// The Act 5 resource group: a scheduler, a task hub, and the one role the laptop's worker needs.

param location string
param tags object
@minLength(3)
param token string
param principalId string
param schedulerSku string

resource scheduler 'Microsoft.DurableTask/schedulers@2025-11-01' = {
  name: 'act5-dts-${token}'
  location: location
  tags: tags
  properties: {
    // The worker dials in from a conference network whose egress address is not known in advance.
    ipAllowlist: ['0.0.0.0/0']
    // Consumption is rejected outright if `capacity` is present; only Dedicated is sized.
    sku: schedulerSku == 'Consumption' ? { name: schedulerSku } : { name: schedulerSku, capacity: 1 }
  }
}

// Named `lipica`, not `default`: the endpoint alone then says which hub the demo is talking to,
// and a stray emulator config cannot silently point at the cloud hub.
resource taskHub 'Microsoft.DurableTask/schedulers/taskHubs@2025-11-01' = {
  parent: scheduler
  name: 'lipica'
  properties: {}
}

// The worker and the client both run on the laptop as the signed-in user, so that identity needs
// data-plane access. The template grants it to the principal that runs `azd provision`.
var dtsDataContributor = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '0ad04412-c4d5-4796-b79c-f76d14c8d402'
)

resource userAccess 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: scheduler
  name: guid(scheduler.id, principalId, dtsDataContributor)
  properties: {
    roleDefinitionId: dtsDataContributor
    principalId: principalId
    principalType: 'User'
  }
}

output schedulerEndpoint string = scheduler.properties.endpoint
output taskHubName string = taskHub.name
output dashboardUrl string = 'https://portal.azure.com/#@/resource${scheduler.id}/taskHubs'
