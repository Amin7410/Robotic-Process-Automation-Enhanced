using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Text.Json.Serialization;
using System.Text.Json.Nodes;

namespace server
{
    public class ClientRequest
    {
        [JsonPropertyName("Command")]
        public string? Command { get; set; }

        [JsonPropertyName("Params")]
        public JsonNode? Params { get; set; }
    }

    public class ServerResponse
    {
        [JsonPropertyName("Status")]
        public string? Status { get; set; }

        [JsonPropertyName("Message")]
        public string? Message { get; set; }

        [JsonPropertyName("Result")]
        public JsonNode? Result { get; set; }
    }
}
