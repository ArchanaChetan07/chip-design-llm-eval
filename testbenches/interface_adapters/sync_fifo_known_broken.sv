// testbenches/interface_adapters/sync_fifo_known_broken.sv
// Intentionally broken: full flag computed one entry too late, allowing a
// write to silently overwrite unread data (classic FIFO off-by-one).
module sync_fifo #(
    parameter WIDTH = 8,
    parameter DEPTH = 4
) (
    input  logic clk, rst_n,
    input  logic wr_en, rd_en,
    input  logic [WIDTH-1:0] wr_data,
    output logic [WIDTH-1:0] rd_data,
    output logic full, empty
);
    localparam PTR_W = $clog2(DEPTH);
    logic [WIDTH-1:0] mem [0:DEPTH-1];
    logic [PTR_W:0] wr_ptr, rd_ptr;

    // BUG: uses only lower bits, never distinguishes "full" from "empty"
    // wraparound -- both report the pointers-equal condition as empty,
    // so full is never correctly asserted and writes silently overwrite.
    assign full  = 1'b0;  // BUG: never signals full
    assign empty = (wr_ptr == rd_ptr);
    assign rd_data = mem[rd_ptr[PTR_W-1:0]];

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wr_ptr <= 0;
            rd_ptr <= 0;
        end else begin
            if (wr_en) begin  // BUG: doesn't check !full, always writes
                mem[wr_ptr[PTR_W-1:0]] <= wr_data;
                wr_ptr <= wr_ptr + 1;
            end
            if (rd_en && !empty) begin
                rd_ptr <= rd_ptr + 1;
            end
        end
    end
endmodule
